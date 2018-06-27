#!/bin/bash

GPU_ID=1
for i in $(seq 12500 10 14990)
do
CUDA_VISIBLE_DEVICES=$GPU_ID blender --background --python render_sc_images_drop.py -- --width 480 --height 320 --num_images 10 --start_idx $i --use_gpu 1 --camera_jitter 1.0
done
