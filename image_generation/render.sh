#!/bin/bash

GPU_ID=3
for i in $(seq 14500 10 14990)
do
CUDA_VISIBLE_DEVICES=$GPU_ID blender --background --python render_sc_images_color.py -- --output_image_dir ../output_color/images/ --semantic_output_image_dir ../output_color/sc_images/ --nonsemantic_output_image_dir ../output_color/nsc_images/ --output_scene_dir ../output_color/scenes/ --semantic_output_scene_dir ../output_color/sc_scenes --nonsemantic_output_scene_dir ../output_color/nsc_scenes/ --output_scene_file ../output_color/CLEVR_scenes.json --semantic_output_scene_file ../output_color/CLEVR_sc_scenes.json --nonsemantic_output_scene_file ../output_color/CLEVR_nsc_scenes.json --output_blend_dir ../output_color/blendfiles --semantic_output_blend_dir ../output_color/sc_blendfiles --nonsemantic_output_blend_dir ../output_color/nsc_blendfiles --width 480 --height 320 --num_images 10 --start_idx $i --use_gpu 1 --camera_jitter 1.0 --shape_color_combos_json ./data/CoGenT_A.json
done
