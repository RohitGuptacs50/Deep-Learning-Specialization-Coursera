# -*- coding: utf-8 -*-
"""yolo_Coursera.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1t_TSrp9O80X7R52EuwyTe4GpvmOvAuqo
"""

import argparse
import os
import matplotlib.pyplot as plt
from matplotlib.pyplot import imshow
import scipy.io
import scipy.misc
import numpy as np
import pandas as pd
import PIL
import tensorflow as tf
from tensorflow.keras import backend as K
from tensorflow.keras.layers import Input, Lambda, Conv2D
from tensorflow.keras.models import load_model, Model

import os
import pprint # for pretty printing our device stats

if 'COLAB_TPU_ADDR' not in os.environ:
    print('ERROR: Not connected to a TPU runtime; please see the first cell in this notebook for instructions!')
else:
    tpu_address = 'grpc://' + os.environ['COLAB_TPU_ADDR']
    print ('TPU address is', tpu_address)

    with tf.compat.v1.Session(tpu_address) as session:
      devices = session.list_devices()

    print('TPU devices:')
    pprint.pprint(devices)

tf.config.experimental_connect_to_host('grpc://' + os.environ['COLAB_TPU_ADDR'])
resolver = tf.distribute.cluster_resolver.TPUClusterResolver('grpc://' + os.environ['COLAB_TPU_ADDR'])
tf.tpu.experimental.initialize_tpu_system(resolver)
strategy = tf.distribute.experimental.TPUStrategy(resolver)

from google.colab import files
src = list(files.upload().values())[0]
open('/content/drive/MyDrive/Colab Notebooks/Yolo/Yolo_Coursera/yolo_utils.py','wb').write(src)
import yolo_utils

from yolo_utils import read_classes, read_anchors, generate_colors, preprocess_image, draw_boxes, scale_boxes

!git clone https://github.com/allanzelener/yad2k.git

from yad2k.yad2k.models.keras_yolo import yolo_head, yolo_boxes_to_corners, preprocess_true_boxes, yolo_loss, yolo_body

def yolo_filter_boxes(box_confidence, boxes, box_class_probs, threshold = 0.6):
    """Filters YOLO boxes by thresholding on object and class confidence.
    
    Arguments:
    box_confidence -- tensor of shape (19, 19, 5, 1),  some object(1) for each of the 5 boxes in each of the 19 * 19 cells  
    boxes -- tensor of shape (19, 19, 5, 4)   , height, width, x and y coordinate for each of the 5 boxes for each of the 19 * 19 cells
    box_class_probs -- tensor of shape (19, 19, 5, 80)   for each of the 5 boxes of each 19 *19 cell, detection probabilities for each of the 80 objects(classes) 
    threshold -- real value, if [ highest class probability score < threshold], then get rid of the corresponding box
    
    Returns:
    scores -- tensor of shape (None,), containing the class probability score for selected boxes
    boxes -- tensor of shape (None, 4), containing (b_x, b_y, b_h, b_w) coordinates of selected boxes
    classes -- tensor of shape (None,), containing the index of the class detected by the selected boxes
    
    Note: "None" is here because you don't know the exact number of selected boxes, as it depends on the threshold. 
    For example, the actual output size of scores would be (10,) if there are 10 boxes.
    """

    # Compute box scores
    box_scores = box_confidence * box_class_probs  # 19x19x5x80

    # Find the box_classes using the max box_scores, keep track of the corresponding score
    box_classes = K.argmax(box_scores, axis=-1)     # argmax returns the index of the maximal value 19x19x5x1
    box_class_scores = K.max(box_scores, axis=-1)   # max = returns the maximal value      19x19x5x1

    # Step 3: Create a filtering mask based on "box_class_scores" by using "threshold". The mask should have the
    # same dimension as box_class_scores, and be True for the boxes you want to keep (with probability >= threshold)
    filtering_mask = (box_class_scores >= threshold)

    #Apply the mask to box_class_scores, boxes and box_classes
    scores = tf.boolean_mask(box_class_scores, filtering_mask)
    boxes = tf.boolean_mask(boxes, filtering_mask)
    classes = tf.boolean_mask(box_classes, filtering_mask)

    return scores, boxes, classes, box_scores

import tensorflow as tf
with tf.compat.v1.Session() as test_a:
    box_confidence = tf.random.normal([19, 19, 5, 1], mean=1, stddev=4, seed=1)
    boxes = tf.random.normal([19, 19, 5, 4], mean=1, stddev=4, seed=1)
    box_class_probs = tf.random.normal([19, 19, 5, 80], mean=1, stddev=4, seed=1)
    scores, boxes, classes, box_scores = yolo_filter_boxes(box_confidence, boxes, box_class_probs, threshold=0.5)
    
    print("scores[2] = " + str(scores[2].eval()))
    print("boxes[2] = " + str(boxes[2].eval()))
    print("classes[2] = " + str(classes[2].eval()))
    print("scores.shape = " + str(scores.shape))
    print("boxes.shape = " + str(boxes.shape))
    print("classes.shape = " + str(classes.shape))
    print(box_scores.shape)

def iou(box1, box2):
  """Implement the intersection over union (IoU) between box1 and box2
    
    Arguments:
    box1 -- first box, list object with coordinates (box1_x1, box1_y1, box1_x2, box_1_y2)
    box2 -- second box, list object with coordinates (box2_x1, box2_y1, box2_x2, box2_y2)
    """
  # Assign variable names to coordinates for clarity
  (box1_x1, box1_y1, box1_x2, box1_y2) = box1
  (box2_x1, box2_y1, box2_x2, box2_y2) = box2
  # Calculate the (yi1, xi1, yi2, xi2) coordinates of the intersection of box1 and box2. Calculate its Area.
  xi1 = np.maximum(box1[0], box2[0])
  #yi1 = maximum of the y1 coordinates of the two boxes
  yi1 = np.maximum(box1[1], box2[1])
  #xi2 = minimum of the x2 coordinates of the two boxes
  xi2 = np.minimum(box1[2], box2[2])
  #yi2 = minimum of the y2 coordinates of the two boxes
  yi2 = np.minimum(box1[3], box2[3])
  inter_width = (xi2-xi1)
  inter_height =(yi2-yi1)
  inter_area = (xi2-xi1)*(yi2-yi1)

  # Calculate the Union area by using Formula: Union(A,B) = A + B - Inter(A,B)
  box1_area = (box1[2]-box1[0])*(box1[3]-box1[1])
  box2_area = (box2[2]-box2[0])*(box2[3]-box2[1])
  union_area = box1_area+box2_area-inter_area

  # compute the IoU
  iou = inter_area/union_area

  return iou

## Test case 1: boxes intersect
box1 = (2, 1, 4, 3)
box2 = (1, 2, 3, 4) 
print("iou for intersecting boxes = " + str(iou(box1, box2)))

## Test case 2: boxes do not intersect
box1 = (1,2,3,4)
box2 = (5,6,7,8)
print("iou for non-intersecting boxes = " + str(iou(box1,box2)))

## Test case 3: boxes intersect at vertices only
box1 = (1,1,2,2)
box2 = (2,2,3,3)
print("iou for boxes that only touch at vertices = " + str(iou(box1,box2)))

## Test case 4: boxes intersect at edge only
box1 = (1,1,3,3)
box2 = (2,3,3,4)
print("iou for boxes that only touch at edges = " + str(iou(box1,box2)))

def yolo_non_max_suppression(scores, boxes, classes, max_boxes = 10, iou_threshold = 0.5):
  """
    Applies Non-max suppression (NMS) to set of boxes
    
    Arguments:
    scores -- tensor of shape (None,), output of yolo_filter_boxes()
    boxes -- tensor of shape (None, 4), output of yolo_filter_boxes() that have been scaled to the image size (see later)
    classes -- tensor of shape (None,), output of yolo_filter_boxes()
    max_boxes -- integer, maximum number of predicted boxes you'd like
    iou_threshold -- real value, "intersection over union" threshold used for NMS filtering
    
    Returns:
    scores -- tensor of shape (, None), predicted score for each box
    boxes -- tensor of shape (4, None), predicted box coordinates
    classes -- tensor of shape (, None), predicted class for each box
    
    Note: The "None" dimension of the output tensors has obviously to be less than max_boxes. Note also that this
    function will transpose the shapes of scores, boxes, classes. This is made for convenience.
    """
  max_boxes_tensor = K.variable(max_boxes, dtype='int32')   # tensor to be used in tf.image.non_max_suppression
  tf.compat.v1.keras.backend.get_session().run(tf.compat.v1.variables_initializer([max_boxes_tensor]))   # Initialize variable max_boxes_tensor

  # Use tf.image.non_max_suppression() to get the list of indices corresponding to boxes you keep
  nms_indices = tf.image.non_max_suppression(boxes, scores, max_boxes_tensor, iou_threshold=iou_threshold)

  # Use K.gather() to select only nms_indices from scores, boxes and classes
  scores = K.gather(scores,nms_indices)
  boxes = K.gather(boxes,nms_indices)
  classes = K.gather(classes,nms_indices)

  return scores, boxes, classes

with tf.compat.v1.Session() as test_b:
    scores = tf.random.normal([54,], mean=1, stddev=4, seed = 1)
    boxes = tf.random.normal([54, 4], mean=1, stddev=4, seed = 1)
    classes = tf.random.normal([54,], mean=1, stddev=4, seed = 1)
    scores, boxes, classes = yolo_non_max_suppression(scores, boxes, classes)
    print("scores[2] = " + str(scores[2].eval()))
    print("boxes[2] = " + str(boxes[2].eval()))
    print("classes[2] = " + str(classes[2].eval()))
    print("scores.shape = " + str(scores.eval().shape))
    print("boxes.shape = " + str(boxes.eval().shape))
    print("classes.shape = " + str(classes.eval().shape))

def yolo_eval(box_confidence, box_xy, box_wh, box_class_probs, image_shape = (720., 1280.), max_boxes = 10, score_threshold = 0.6, iou_threshold = 0.5):
  """
    Converts the output of YOLO encoding (a lot of boxes) to your predicted boxes along with their scores, box coordinates and classes.
    
    Arguments:
    yolo_outputs -- output of the encoding model (for image_shape of (608, 608, 3)), contains 4 tensors:
                    box_confidence: tensor of shape (None, 19, 19, 5, 1)
                    box_xy: tensor of shape (None, 19, 19, 5, 2)
                    box_wh: tensor of shape (None, 19, 19, 5, 2)
                    box_class_probs: tensor of shape (None, 19, 19, 5, 80)
    image_shape -- tensor of shape (2,) containing the input shape, in this notebook we use (608., 608.) (has to be float32 dtype)
    max_boxes -- integer, maximum number of predicted boxes you'd like
    score_threshold -- real value, if [ highest class probability score < threshold], then get rid of the corresponding box
    iou_threshold -- real value, "intersection over union" threshold used for NMS filtering
    
    Returns:
    scores -- tensor of shape (None, ), predicted score for each box
    boxes -- tensor of shape (None, 4), predicted box coordinates
    classes -- tensor of shape (None,), predicted class for each box
  """
    

    # Convert boxes to be ready for filtering functions (convert boxes box_xy and box_wh to corner coordinates)
  boxes = yolo_boxes_to_corners(box_xy, box_wh)

    # Function to perform Score-filtering with a threshold of score_threshold
  scores, boxes, classes = yolo_filter_boxes(box_confidence, boxes, box_class_probs, threshold = score_threshold)

    # Scale boxes back to original image shape.
  boxes = scale_boxes(boxes, image_shape)

    # perform Non-max suppression with 
    # maximum number of boxes set to max_boxes and a threshold of iou_threshold
  scores, boxes, classes = yolo_non_max_suppression(scores, boxes, classes, max_boxes=max_boxes, iou_threshold=iou_threshold)

  return scores, boxes, classes

with tf.compat.v1.Session() as test_b:
    box_confidence = tf.random.normal([19, 19, 5, 1], mean=1, stddev=4, seed = 1)
    box_xy = tf.random.normal([19, 19, 5, 2], mean=1, stddev=4, seed = 1)
    box_wh = tf.random.normal([19, 19, 5, 2], mean=1, stddev=4, seed = 1)
    box_class_probs = tf.random.normal([19, 19, 5, 80], mean=1, stddev=4, seed = 1)
    scores, boxes, classes = yolo_eval(box_confidence, box_xy, box_wh, box_class_probs)
    print("scores[2] = " + str(scores[2].eval()))
    print("boxes[2] = " + str(boxes[2].eval()))
    print("classes[2] = " + str(classes[2].eval()))
    print("scores.shape = " + str(scores.eval().shape))
    print("boxes.shape = " + str(boxes.eval().shape))
    print("classes.shape = " + str(classes.eval().shape))

sess = tf.compat.v1.keras.backend.get_session()

class_names = read_classes('/content/drive/MyDrive/Colab Notebooks/Yolo/Yolo_Coursera/coco_classes.txt')
anchors = read_anchors('/content/drive/MyDrive/Colab Notebooks/Yolo/Yolo_Coursera/yolo_anchors.txt')
image_shape = (720., 1280.)

print(anchors)

!unzip "/content/drive/MyDrive/Colab Notebooks/Yolo/Yolo_Coursera/yolo.zip" -d "/content/drive/MyDrive/Colab Notebooks/Yolo/Yolo_Coursera/yolomodelfile"

yolo_model = load_model("/content/drive/MyDrive/Colab Notebooks/Yolo/Yolo_Coursera/yolomodelfile/yolo.h5")

yolo_model.summary()

yolo_outputs = yolo_head(yolo_model.output, anchors, len(class_names))

scores, boxes, classes = yolo_eval(yolo_outputs, image_shape)

def predict(sess, image_file):


  image, image_data = preprocess_image('images/' + image_file, model_image_size = (608, 608))

  out_scores, out_boxes, out_classes = sess.run([scores, boxes, classes], feed_dict={yolo_model.input:image_data, K.learning_phase():0})
  ### END CODE HERE ###

  print('Found {} boxes for {}'.format(len(out_boxes), image_file))

  colors = generate_colors(class_names)

  draw_boxes(image, out_scores, out_boxes, out_classes, class_names, colors)

  image.save(os.path.join('out', image_file), quality = 90)

  output_image = scipy.misc.imread(os.path.join('out', image_file))
  imshow(output_image)

  return out_scores, out_boxes, out_classes

out_scores, out_boxes, out_classes = predict(sess, "test.jpg")


