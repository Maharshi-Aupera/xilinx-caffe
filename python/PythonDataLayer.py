# (c) Copyright 2019 Xilinx, Inc. All rights reserved.
#
# This file contains confidential and proprietary information
# of Xilinx, Inc. and is protected under U.S. and
# international copyright and other intellectual property
# laws.
#
# DISCLAIMER
# This disclaimer is not a license and does not grant any
# rights to the materials distributed herewith. Except as
# otherwise provided in a valid license issued to you by
# Xilinx, and to the maximum extent permitted by applicable
# law: (1) THESE MATERIALS ARE MADE AVAILABLE "AS IS" AND
# WITH ALL FAULTS, AND XILINX HEREBY DISCLAIMS ALL WARRANTIES
# AND CONDITIONS, EXPRESS, IMPLIED, OR STATUTORY, INCLUDING
# BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, NON-
# INFRINGEMENT, OR FITNESS FOR ANY PARTICULAR PURPOSE; and
# (2) Xilinx shall not be liable (whether in contract or tort,
# including negligence, or under any other theory of
# liability) for any loss or damage of any kind or nature
# related to, arising under or in connection with these
# materials, including for any direct, or any indirect,
# special, incidental, or consequential loss or damage
# (including loss of data, profits, goodwill, or any type of
# loss or damage suffered as a result of any action brought
# by a third party) even if such damage or loss was
# reasonably foreseeable or Xilinx had been advised of the
# possibility of the same.
#
# CRITICAL APPLICATIONS
# Xilinx products are not designed or intended to be fail-
# safe, or for use in any application requiring fail-safe
# performance, such as life-support or safety devices or
# systems, Class III medical devices, nuclear facilities,
# applications related to the deployment of airbags, or any
# other applications that could lead to death, personal
# injury, or severe property or environmental damage
# (individually and collectively, "Critical
# Applications"). Customer assumes the sole risk and
# liability of any use of Xilinx products in Critical
# Applications, subject only to applicable laws and
# regulations governing limitations on product liability.
#
# THIS COPYRIGHT NOTICE AND DISCLAIMER MUST BE RETAINED AS
# PART OF THIS FILE AT ALL TIMES.

#!/usr/bin/python2
#-*-coding:utf-8-*-
import sys
caffe_root = '/opt/caffe/'
sys.path.insert(0, caffe_root + 'python')
import caffe
import cv2
import numpy as np
import os
import random
import re
import copy

################################################################################
#########################Data Layer By Python###################################
################################################################################
def GenerateAnnotation(image_name = None,
                       points = None,
                       sex = None,
                       age = None):
    assert image_name != None
    # points regression
    if points != None:
        points_mask = [1] * 10
    else:
        points = [0] * 10
        points_mask = [0] * 10
    # sex classification
    if sex != None:
        sex_mask = [1] * 2
    else:
        sex = [0]
        sex_mask = [0] * 2
    # age regression
    if age != None:
        age_mask = [1] * 2
    else:
        age = [0]
        age_mask = [0] * 2
    return (image_name, points, points_mask, sex, sex_mask, age, age_mask)

def IndexGenerate(L, phase):
    while True:
        l = np.arange(L)
        if phase == caffe.TRAIN:
            np.random.shuffle(l)
        for i in l:
            yield i

class DataLoader(object):
    def __init__(self,\
                 align_dataset_root, align_dataset_file,\
                 sex_age_dataset_root, sex_age_dataset_file,\
                 phase):
        # align and sex_age annotation
        self.mean_value = 127.5
        self.scale = 0.00784315
        self.im_shape = (96, 72, 3)
        self.annotation_list = []
        # align annotation
        assert os.path.exists(align_dataset_file)
        fp = open(align_dataset_file, 'r')
        lines = fp.readlines()
        fp.close()
        for line in lines:
            line = line.strip('\n').split(' ')
            print("Hello -------------------------------------- >>>")
            image_name = align_dataset_root + line[0] #+ '.jpg'
            points = np.array(line[1:], dtype = np.float).tolist()
            assert os.path.exists(image_name)
            self.annotation_list.append(GenerateAnnotation(image_name = image_name,
                                                           points = points))
        # sex and age annotation
        assert os.path.exists(sex_age_dataset_file)
        fp = open(sex_age_dataset_file, 'r')
        lines = fp.readlines()
        fp.close()
        for line in lines:
            image_name = os.path.join(sex_age_dataset_root, line.strip())
            line = line.replace('female', '0')
            line = line.replace('male', '1')
            if re.match('\d+_\d+_\d+.jpg\n', line):
                line = line.strip('\n')[:-4].split('_')
                sex = [int(line[2])]
                age = [int(line[1])]
            elif re.match(u'[\dA-Z]+_[12]{1}_\d{1,2}_[01]{1}.jpg\n', line):
                line = line.strip()[:-4].split('_')
                sex = [int(line[3])]
                age = [int(line[2])]
            else:
                assert 0
            assert os.path.exists(image_name)
            assert sex in [[0], [1]]
            self.annotation_list.append(GenerateAnnotation(image_name = image_name,
                                                           sex = sex,
                                                           age = age))
        self.index_generate = IndexGenerate(len(self.annotation_list), phase)

    def load_next_image(self):
        index = self.index_generate.next()
        annotation = self.annotation_list[index]
        img_name = annotation[0]
        img = cv2.imread(img_name)
        # img = img.astype(np.float)
        # img = cv2.reshape(img, (72, 96))
        assert img.shape == self.im_shape
        img = img.astype(np.float)
        img = img.transpose(2, 0, 1)
        # norm for image
        img = img - self.mean_value
        img = img * self.scale
        # points
        points = copy.deepcopy(annotation[1])
        points_mask = copy.deepcopy(annotation[2])
        for i in range(5):
            points[i] = points[i]
            points[i + 5] = points[i + 5]
#            points[i] = points[i] / float(self.im_shape[1])
#            points[i + 5] = points[i + 5] / float(self.im_shape[0])
        # sex
        sex = copy.deepcopy(annotation[3])
        sex_mask = copy.deepcopy(annotation[4])
        # age
        age = copy.deepcopy(annotation[5])
        age_mask = copy.deepcopy(annotation[6])
#        age[0] = age[0]
#        age[0] = age[0] / float(60.)
        # return
        return img, points, points_mask, sex, sex_mask, age, age_mask

class AttrDataLayer(caffe.Layer):
    def setup(self, bottom, top):
        # batch_size, align_dataset_root, align_dataset_file, sex_age_dataset_root, sex_age_dataset_file different in train and test
        # self.phase TRAIN = 0, TEST = 1
        self.batch_size = [2, 1][self.phase]
        params_str = eval(self.param_str)
        print("Hi")
        align_dataset_root = [params_str['landmark_train_path']+'/', params_str['landmark_test_path']+'/'][self.phase]
        align_dataset_file = [params_str['landmark_train_list'], params_str['landmark_test_list']][self.phase]
        sex_age_dataset_root = [params_str['age_sex_train_path']+'/', params_str['age_sex_test_path']+'/'][self.phase]
        sex_age_dataset_file = [params_str['age_sex_train_list'], params_str['age_sex_test_list']][self.phase]
        # loader
        self.batch_loader = DataLoader(align_dataset_root, align_dataset_file, sex_age_dataset_root, sex_age_dataset_file, self.phase)
        # output blob
        top[0].reshape(self.batch_size, 3, 96, 72)
        top[1].reshape(self.batch_size, 10)
        top[2].reshape(self.batch_size, 10)
        top[3].reshape(self.batch_size, 1)
        top[4].reshape(self.batch_size, 2)
        top[5].reshape(self.batch_size, 1)
        top[6].reshape(self.batch_size, 2)

    def reshape(self, bottom, top):
        pass

    def forward(self, bottom, top):
        for i in range(self.batch_size):
            img, points, points_mask, sex, sex_mask, age, age_mask = self.batch_loader.load_next_image()
            top[0].data[i, ...] = img
            top[1].data[i, ...] = points
            top[2].data[i, ...] = points_mask
            top[3].data[i, ...] = sex
            top[4].data[i, ...] = sex_mask
            top[5].data[i, ...] = age
            top[6].data[i, ...] = age_mask

    def backward(self, top, propagate_down, bottom):
        pass
