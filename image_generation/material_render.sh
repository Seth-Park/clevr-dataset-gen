#!/bin/bash

GPU_ID=6
for i in $(seq 57500 10 59990)
do
CUDA_VISIBLE_DEVICES=$GPU_ID blender --background --python render_sc_images_material.py -- --output_image_dir ../output_material/images/ --semantic_output_image_dir ../output_material/sc_images/ --nonsemantic_output_image_dir ../output_material/nsc_images/ --output_scene_dir ../output_material/scenes/ --semantic_output_scene_dir ../output_material/sc_scenes --nonsemantic_output_scene_dir ../output_material/nsc_scenes/ --output_scene_file ../output_material/CLEVR_scenes.json --semantic_output_scene_file ../output_material/CLEVR_sc_scenes.json --nonsemantic_output_scene_file ../output_material/CLEVR_nsc_scenes.json --output_blend_dir ../output_material/blendfiles --semantic_output_blend_dir ../output_material/sc_blendfiles --nonsemantic_output_blend_dir ../output_material/nsc_blendfiles --width 480 --height 320 --num_images 10 --start_idx $i --use_gpu 1 --camera_jitter 1.0 --shape_color_combos_json ./data/CoGenT_A.json
done
