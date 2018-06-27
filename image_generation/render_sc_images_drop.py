# Copyright 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from __future__ import print_function
import math, sys, random, argparse, json, os, tempfile, copy
from datetime import datetime as dt
from collections import Counter

"""
Renders random scenes using Blender, each with with a random number of objects;
each object has a random size, position, color, and shape. Objects will be
nonintersecting but may partially occlude each other. Output images will be
written to disk as PNGs, and we will also write a JSON file for each image with
ground-truth scene information.

This file expects to be run from Blender like this:

blender --background --python render_images.py -- [arguments to this script]
"""

INSIDE_BLENDER = True
try:
  import bpy, bpy_extras
  from mathutils import Vector
except ImportError as e:
  INSIDE_BLENDER = False
if INSIDE_BLENDER:
  try:
    import utils
  except ImportError as e:
    print("\nERROR")
    print("Running render_images.py from Blender and cannot import utils.py.") 
    print("You may need to add a .pth file to the site-packages of Blender's")
    print("bundled python with a command like this:\n")
    print("echo $PWD >> $BLENDER/$VERSION/python/lib/python3.5/site-packages/clevr.pth")
    print("\nWhere $BLENDER is the directory where Blender is installed, and")
    print("$VERSION is your Blender version (such as 2.78).")
    sys.exit(1)

parser = argparse.ArgumentParser()

# Input options
parser.add_argument('--base_scene_blendfile', default='data/base_scene.blend',
    help="Base blender file on which all scenes are based; includes " +
          "ground plane, lights, and camera.")
parser.add_argument('--properties_json', default='data/properties.json',
    help="JSON file defining objects, materials, sizes, and colors. " +
         "The \"colors\" field maps from CLEVR color names to RGB values; " +
         "The \"sizes\" field maps from CLEVR size names to scalars used to " +
         "rescale object models; the \"materials\" and \"shapes\" fields map " +
         "from CLEVR material and shape names to .blend files in the " +
         "--object_material_dir and --shape_dir directories respectively.")
parser.add_argument('--shape_dir', default='data/shapes',
    help="Directory where .blend files for object models are stored")
parser.add_argument('--material_dir', default='data/materials',
    help="Directory where .blend files for materials are stored")
parser.add_argument('--shape_color_combos_json', default=None,
    help="Optional path to a JSON file mapping shape names to a list of " +
         "allowed color names for that shape. This allows rendering images " +
         "for CLEVR-CoGenT.")

# Settings for objects
parser.add_argument('--min_objects', default=3, type=int,
    help="The minimum number of objects to place in each scene")
parser.add_argument('--max_objects', default=10, type=int,
    help="The maximum number of objects to place in each scene")
parser.add_argument('--min_dist', default=0.25, type=float,
    help="The minimum allowed distance between object centers")
parser.add_argument('--margin', default=0.4, type=float,
    help="Along all cardinal directions (left, right, front, back), all " +
         "objects will be at least this distance apart. This makes resolving " +
         "spatial relationships slightly less ambiguous.")
parser.add_argument('--min_pixels_per_object', default=200, type=int,
    help="All objects will have at least this many visible pixels in the " +
         "final rendered images; this ensures that no objects are fully " +
         "occluded by other objects.")
parser.add_argument('--max_retries', default=50, type=int,
    help="The number of times to try placing an object before giving up and " +
         "re-placing all objects in the scene.")

# Output settings
parser.add_argument('--start_idx', default=0, type=int,
    help="The index at which to start for numbering rendered images. Setting " +
         "this to non-zero values allows you to distribute rendering across " +
         "multiple machines and recombine the results later.")
parser.add_argument('--num_images', default=5, type=int,
    help="The number of images to render")
parser.add_argument('--filename_prefix', default='CLEVR',
    help="This prefix will be prepended to the rendered images and JSON scenes")
parser.add_argument('--split', default='default',
    help="Name of the split for which we are rendering. This will be added to " +
         "the names of rendered images, and will also be stored in the JSON " +
         "scene structure for each image.")
parser.add_argument('--semantic_split', default='semantic',
    help="Name of the split for which we are rendering. This will be added to " +
         "the names of rendered images, and will also be stored in the JSON " +
         "scene structure for each image.")
parser.add_argument('--nonsemantic_split', default='nonsemantic',
    help="Name of the split for which we are rendering. This will be added to " +
         "the names of rendered images, and will also be stored in the JSON " +
         "scene structure for each image.")
parser.add_argument('--output_image_dir', default='../output_drop/images/',
    help="The directory where output images will be stored. It will be " +
         "created if it does not exist.")
parser.add_argument('--semantic_output_image_dir', default='../output_drop/sc_images/',
    help="The directory where output images will be stored. It will be " +
         "created if it does not exist.")
parser.add_argument('--nonsemantic_output_image_dir', default='../output_drop/nsc_images/',
    help="The directory where output images will be stored. It will be " +
         "created if it does not exist.")
parser.add_argument('--output_scene_dir', default='../output_drop/scenes/',
    help="The directory where output JSON scene structures will be stored. " +
         "It will be created if it does not exist.")
parser.add_argument('--semantic_output_scene_dir', default='../output_drop/sc_scenes/',
    help="The directory where output JSON scene structures will be stored. " +
         "It will be created if it does not exist.")
parser.add_argument('--nonsemantic_output_scene_dir', default='../output_drop/nsc_scenes/',
    help="The directory where output JSON scene structures will be stored. " +
         "It will be created if it does not exist.")
parser.add_argument('--output_scene_file', default='../output_drop/CLEVR_scenes.json',
    help="Path to write a single JSON file containing all scene information")
parser.add_argument('--semantic_output_scene_file', default='../output_drop/CLEVR_sc_scenes.json',
    help="Path to write a single JSON file containing all scene information")
parser.add_argument('--nonsemantic_output_scene_file', default='../output_drop/CLEVR_nsc_scenes.json',
    help="Path to write a single JSON file containing all scene information")
parser.add_argument('--output_blend_dir', default='../output_drop/blendfiles',
         help="The directory where blender scene files will be stored, if the " +
         "user requested that these files be saved using the " +
         "--save_blendfiles flag; in this case it will be created if it does " +
         "not already exist.")
parser.add_argument('--semantic_output_blend_dir', default='../output_drop/sc_blendfiles',
         help="The directory where blender scene files will be stored, if the " +
         "user requested that these files be saved using the " +
         "--save_blendfiles flag; in this case it will be created if it does " +
         "not already exist.")
parser.add_argument('--nonsemantic_output_blend_dir', default='../output_drop/nsc_blendfiles',
         help="The directory where blender scene files will be stored, if the " +
         "user requested that these files be saved using the " +
         "--save_blendfiles flag; in this case it will be created if it does " +
         "not already exist.")
parser.add_argument('--save_blendfiles', type=int, default=0,
    help="Setting --save_blendfiles 1 will cause the blender scene file for " +
         "each generated image to be stored in the directory specified by " +
         "the --output_blend_dir flag. These files are not saved by default " +
         "because they take up ~5-10MB each.")
parser.add_argument('--version', default='1.0',
    help="String to store in the \"version\" field of the generated JSON file")
parser.add_argument('--license',
    default="Creative Commons Attribution (CC-BY 4.0)",
    help="String to store in the \"license\" field of the generated JSON file")
parser.add_argument('--date', default=dt.today().strftime("%m/%d/%Y"),
    help="String to store in the \"date\" field of the generated JSON file; " +
         "defaults to today's date")

# Rendering options
parser.add_argument('--use_gpu', default=0, type=int,
    help="Setting --use_gpu 1 enables GPU-accelerated rendering using CUDA. " +
         "You must have an NVIDIA GPU with the CUDA toolkit installed for " +
         "to work.")
parser.add_argument('--width', default=320, type=int,
    help="The width (in pixels) for the rendered images")
parser.add_argument('--height', default=240, type=int,
    help="The height (in pixels) for the rendered images")
parser.add_argument('--key_light_jitter', default=1.0, type=float,
    help="The magnitude of random jitter to add to the key light position.")
parser.add_argument('--fill_light_jitter', default=1.0, type=float,
    help="The magnitude of random jitter to add to the fill light position.")
parser.add_argument('--back_light_jitter', default=1.0, type=float,
    help="The magnitude of random jitter to add to the back light position.")
parser.add_argument('--camera_jitter', default=0.5, type=float,
    help="The magnitude of random jitter to add to the camera position")
parser.add_argument('--render_num_samples', default=512, type=int,
    help="The number of samples to use when rendering. Larger values will " +
         "result in nicer images but will cause rendering to take longer.")
parser.add_argument('--render_min_bounces', default=8, type=int,
    help="The minimum number of bounces to use for rendering.")
parser.add_argument('--render_max_bounces', default=8, type=int,
    help="The maximum number of bounces to use for rendering.")
parser.add_argument('--render_tile_size', default=256, type=int,
    help="The tile size to use for rendering. This should not affect the " +
         "quality of the rendered image but may affect the speed; CPU-based " +
         "rendering may achieve better performance using smaller tile sizes " +
         "while larger tile sizes may be optimal for GPU-based rendering.")

def main(args):
  num_digits = 6
  prefix = '%s_%s_' % (args.filename_prefix, args.split)
  sc_prefix = '%s_%s_' % (args.filename_prefix, args.semantic_split)
  nsc_prefix = '%s_%s_' % (args.filename_prefix, args.nonsemantic_split)

  img_template = '%s%%0%dd.png' % (prefix, num_digits)
  scene_template = '%s%%0%dd.json' % (prefix, num_digits)
  blend_template = '%s%%0%dd.blend' % (prefix, num_digits)

  sc_img_template = '%s%%0%dd.png' % (sc_prefix, num_digits)
  sc_scene_template = '%s%%0%dd.json' % (sc_prefix, num_digits)
  sc_blend_template = '%s%%0%dd.blend' % (sc_prefix, num_digits)

  nsc_img_template = '%s%%0%dd.png' % (nsc_prefix, num_digits)
  nsc_scene_template = '%s%%0%dd.json' % (nsc_prefix, num_digits)
  nsc_blend_template = '%s%%0%dd.blend' % (nsc_prefix, num_digits)

  default_img_template = os.path.join(args.output_image_dir, img_template)
  default_scene_template = os.path.join(args.output_scene_dir, scene_template)
  default_blend_template = os.path.join(args.output_blend_dir, blend_template)

  semantic_img_template = os.path.join(args.semantic_output_image_dir, sc_img_template)
  semantic_scene_template = os.path.join(args.semantic_output_scene_dir, sc_scene_template)
  semantic_blend_template = os.path.join(args.semantic_output_blend_dir, sc_blend_template)

  nonsemantic_img_template = os.path.join(args.nonsemantic_output_image_dir, nsc_img_template)
  nonsemantic_scene_template = os.path.join(args.nonsemantic_output_scene_dir, nsc_scene_template)
  nonsemantic_blend_template = os.path.join(args.nonsemantic_output_blend_dir, nsc_blend_template)

  if not os.path.isdir(args.output_image_dir):
    os.makedirs(args.output_image_dir)
  if not os.path.isdir(args.output_scene_dir):
    os.makedirs(args.output_scene_dir)
  if args.save_blendfiles == 1 and not os.path.isdir(args.output_blend_dir):
    os.makedirs(args.output_blend_dir)
  
  if not os.path.isdir(args.nonsemantic_output_image_dir):
    os.makedirs(args.nonsemantic_output_image_dir)
  if not os.path.isdir(args.nonsemantic_output_scene_dir):
    os.makedirs(args.nonsemantic_output_scene_dir)
  if args.save_blendfiles == 1 and not os.path.isdir(args.nonsemantic_output_blend_dir):
    os.makedirs(args.nonsemantic_output_blend_dir)

  if not os.path.isdir(args.semantic_output_image_dir):
    os.makedirs(args.semantic_output_image_dir)
  if not os.path.isdir(args.semantic_output_scene_dir):
    os.makedirs(args.semantic_output_scene_dir)
  if args.save_blendfiles == 1 and not os.path.isdir(args.semantic_output_blend_dir):
    os.makedirs(args.semantic_output_blend_dir)
  
  all_scene_paths = []
  all_sc_scene_paths = []
  all_nsc_scene_paths = []
  i = 0
  while i < args.num_images:
    default_img_path = default_img_template % (i + args.start_idx)
    default_scene_path = default_scene_template % (i + args.start_idx)
    default_blend_path = None
    if args.save_blendfiles == 1:
      default_blend_path = default_blend_template % (i + args.start_idx)
    num_objects = random.randint(args.min_objects, args.max_objects)

    # Render default scene.
    default_config = render_default_scene(args,
      num_objects=num_objects,
      output_index=(i + args.start_idx),
      output_split=args.split,
      output_image=default_img_path,
      output_scene=default_scene_path,
      output_blendfile=default_blend_path,
    )

    # Render non-semantically changed scene.
    nonsemantic_img_path = nonsemantic_img_template % (i + args.start_idx)
    nonsemantic_scene_path = nonsemantic_scene_template % (i + args.start_idx)
    nonsemantic_blend_path = None
    if args.save_blendfiles == 1:
      nonsemantic_blend_path = nonsemantic_blend_template % (i + args.start_idx)
    nonsemantic_change_success = render_semantic_change(args, default_config,
      output_index=(i + args.start_idx),
      output_split=args.split,
      output_image=nonsemantic_img_path,
      output_scene=nonsemantic_scene_path,
      output_blendfile=nonsemantic_blend_path,
      change_type='same',
    )

    # Render semantically changed scene.
    semantic_img_path = semantic_img_template % (i + args.start_idx)
    semantic_scene_path = semantic_scene_template % (i + args.start_idx)
    semantic_blend_path = None
    if args.save_blendfiles == 1:
      semantic_blend_path = semantic_blend_template % (i + args.start_idx)
    semantic_change_success = render_semantic_change(args, default_config,
      output_index=(i + args.start_idx),
      output_split=args.split,
      output_image=semantic_img_path,
      output_scene=semantic_scene_path,
      output_blendfile=semantic_blend_path,
      change_type='drop',
    )

    # only save stuffs when semantic and nonsemantic changes succeeded
    if semantic_change_success and nonsemantic_change_success:
      all_scene_paths.append(default_scene_path)
      all_sc_scene_paths.append(semantic_scene_path)
      all_nsc_scene_paths.append(nonsemantic_scene_path)
      i += 1
    # otherwise delete what was generated
    else:
      os.remove(default_img_path)
      os.remove(default_scene_path)
      if default_blend_path is not None:
        os.remove(default_blend_path)
      if nonsemantic_change_success:
        os.remove(nonsemantic_img_path)
        os.remove(nonsemantic_scene_path)
        if nonsemantic_blend_path is not None:
          os.remove(nonsemantic_blend_path)
      if semantic_change_success:
        os.remove(semantic_img_path)
        os.remove(semantic_scene_path)
        if semantic_blend_path is not None:
          os.remove(semantic_blend_path)



  # After rendering all images, combine the JSON files for each scene into a
  # single JSON file.
  all_scenes = []
  for scene_path in all_scene_paths:
    with open(scene_path, 'r') as f:
      all_scenes.append(json.load(f))
  output = {
    'info': {
      'date': args.date,
      'version': args.version,
      'split': args.split,
      'license': args.license,
    },
    'scenes': all_scenes
  }
  with open(args.output_scene_file, 'w') as f:
    json.dump(output, f)

  all_sc_scenes = []
  for scene_path in all_sc_scene_paths:
    with open(scene_path, 'r') as f:
      all_sc_scenes.append(json.load(f))
  output = {
    'info': {
      'date': args.date,
      'version': args.version,
      'split': args.split,
      'license': args.license,
    },
    'scenes': all_sc_scenes
  }
  with open(args.semantic_output_scene_file, 'w') as f:
    json.dump(output, f)

  all_nsc_scenes = []
  for scene_path in all_nsc_scene_paths:
    with open(scene_path, 'r') as f:
      all_nsc_scenes.append(json.load(f))
  output = {
    'info': {
      'date': args.date,
      'version': args.version,
      'split': args.split,
      'license': args.license,
    },
    'scenes': all_nsc_scenes
  }
  with open(args.nonsemantic_output_scene_file, 'w') as f:
    json.dump(output, f)


def render_default_scene(args,
    num_objects=5,
    output_index=0,
    output_split='none',
    output_image='render.png',
    output_scene='render_json',
    output_blendfile=None,
  ):

  # Load the main blendfile
  bpy.ops.wm.open_mainfile(filepath=args.base_scene_blendfile)

  # Load materials
  utils.load_materials(args.material_dir)

  # Set render arguments so we can get pixel coordinates later.
  # We use functionality specific to the CYCLES renderer so BLENDER_RENDER
  # cannot be used.
  render_args = bpy.context.scene.render
  render_args.engine = "CYCLES"
  render_args.filepath = output_image
  render_args.resolution_x = args.width
  render_args.resolution_y = args.height
  render_args.resolution_percentage = 100
  render_args.tile_x = args.render_tile_size
  render_args.tile_y = args.render_tile_size
  if args.use_gpu == 1:
    # Blender changed the API for enabling CUDA at some point
    if bpy.app.version < (2, 78, 0):
      bpy.context.user_preferences.system.compute_device_type = 'CUDA'
      bpy.context.user_preferences.system.compute_device = 'CUDA_0'
    else:
      cycles_prefs = bpy.context.user_preferences.addons['cycles'].preferences
      cycles_prefs.compute_device_type = 'CUDA'

  # Some CYCLES-specific stuff
  bpy.data.worlds['World'].cycles.sample_as_light = True
  bpy.context.scene.cycles.blur_glossy = 2.0
  bpy.context.scene.cycles.samples = args.render_num_samples
  bpy.context.scene.cycles.transparent_min_bounces = args.render_min_bounces
  bpy.context.scene.cycles.transparent_max_bounces = args.render_max_bounces
  if args.use_gpu == 1:
    bpy.context.scene.cycles.device = 'GPU'

  # This will give ground-truth information about the scene and its objects
  scene_struct = {
      'split': output_split,
      'image_index': output_index,
      'image_filename': os.path.basename(output_image),
      'objects': [],
      'directions': {},
  }

  # Put a plane on the ground so we can compute cardinal directions
  bpy.ops.mesh.primitive_plane_add(radius=5)
  plane = bpy.context.object

  def rand(L):
    return 2.0 * L * (random.random() - 0.5)

  config = {}
  # Add random jitter to camera position
  camera_jitters = [] # need this to apply the same jitter for scenes without semantic change
  if args.camera_jitter > 0:
    for i in range(3):
      rand_camera_jitter = rand(args.camera_jitter)
      camera_jitters.append(rand_camera_jitter)
      bpy.data.objects['Camera'].location[i] += rand_camera_jitter
  #config['camera'] = bpy.data.objects['Camera']
  config['camera_jitters'] = camera_jitters

  # Figure out the left, up, and behind directions along the plane and record
  # them in the scene structure
  camera = bpy.data.objects['Camera']
  plane_normal = plane.data.vertices[0].normal
  cam_behind = camera.matrix_world.to_quaternion() * Vector((0, 0, -1))
  cam_left = camera.matrix_world.to_quaternion() * Vector((-1, 0, 0))
  cam_up = camera.matrix_world.to_quaternion() * Vector((0, 1, 0))
  plane_behind = (cam_behind - cam_behind.project(plane_normal)).normalized()
  plane_left = (cam_left - cam_left.project(plane_normal)).normalized()
  plane_up = cam_up.project(plane_normal).normalized()

  # Delete the plane; we only used it for normals anyway. The base scene file
  # contains the actual ground plane.
  utils.delete_object(plane)

  # Save all six axis-aligned directions in the scene struct
  scene_struct['directions']['behind'] = tuple(plane_behind)
  scene_struct['directions']['front'] = tuple(-plane_behind)
  scene_struct['directions']['left'] = tuple(plane_left)
  scene_struct['directions']['right'] = tuple(-plane_left)
  scene_struct['directions']['above'] = tuple(plane_up)
  scene_struct['directions']['below'] = tuple(-plane_up)

  # Add random jitter to lamp positions
  key_light_jitters = []
  back_light_jitters = []
  fill_light_jitters = []
  if args.key_light_jitter > 0:
    for i in range(3):
      rand_key_light_jitter = rand(args.key_light_jitter)
      key_light_jitters.append(rand_key_light_jitter)
      bpy.data.objects['Lamp_Key'].location[i] += rand_key_light_jitter
  if args.back_light_jitter > 0:
    for i in range(3):
      rand_back_light_jitter = rand(args.back_light_jitter)
      back_light_jitters.append(rand_back_light_jitter)
      bpy.data.objects['Lamp_Back'].location[i] += rand_back_light_jitter
  if args.fill_light_jitter > 0:
    for i in range(3):
      rand_fill_light_jitter = rand(args.fill_light_jitter)
      fill_light_jitters.append(rand_fill_light_jitter)
      bpy.data.objects['Lamp_Fill'].location[i] += rand_fill_light_jitter

  config['key_light_jitters'] = key_light_jitters
  config['back_light_jitters'] = back_light_jitters
  config['fill_light_jitters'] = fill_light_jitters

  # Now make some random objects
  objects, blender_objects = add_random_objects(scene_struct, num_objects, args, camera)
  config['objects'] = objects

  # Render the scene and dump the scene data structure
  scene_struct['objects'] = objects
  scene_struct['relationships'] = compute_all_relationships(scene_struct)
  while True:
    try:
      bpy.ops.render.render(write_still=True)
      break
    except Exception as e:
      print(e)

  with open(output_scene, 'w') as f:
    json.dump(scene_struct, f, indent=2)

  if output_blendfile is not None:
    bpy.ops.wm.save_as_mainfile(filepath=output_blendfile)

  return config

def render_semantic_change(args,
    default_config,
    output_index=0,
    output_split='none',
    output_image='render.png',
    output_scene='render_json',
    output_blendfile=None,
    change_type='random',
  ):

  # Load the main blendfile
  bpy.ops.wm.open_mainfile(filepath=args.base_scene_blendfile)

  # Load materials
  utils.load_materials(args.material_dir)

  # Set render arguments so we can get pixel coordinates later.
  # We use functionality specific to the CYCLES renderer so BLENDER_RENDER
  # cannot be used.
  render_args = bpy.context.scene.render
  render_args.engine = "CYCLES"
  render_args.filepath = output_image
  render_args.resolution_x = args.width
  render_args.resolution_y = args.height
  render_args.resolution_percentage = 100
  render_args.tile_x = args.render_tile_size
  render_args.tile_y = args.render_tile_size
  if args.use_gpu == 1:
    # Blender changed the API for enabling CUDA at some point
    if bpy.app.version < (2, 78, 0):
      bpy.context.user_preferences.system.compute_device_type = 'CUDA'
      bpy.context.user_preferences.system.compute_device = 'CUDA_0'
    else:
      cycles_prefs = bpy.context.user_preferences.addons['cycles'].preferences
      cycles_prefs.compute_device_type = 'CUDA'

  # Some CYCLES-specific stuff
  bpy.data.worlds['World'].cycles.sample_as_light = True
  bpy.context.scene.cycles.blur_glossy = 2.0
  bpy.context.scene.cycles.samples = args.render_num_samples
  bpy.context.scene.cycles.transparent_min_bounces = args.render_min_bounces
  bpy.context.scene.cycles.transparent_max_bounces = args.render_max_bounces
  if args.use_gpu == 1:
    bpy.context.scene.cycles.device = 'GPU'

  # This will give ground-truth information about the scene and its objects
  scene_struct = {
      'split': output_split,
      'image_index': output_index,
      'image_filename': os.path.basename(output_image),
      'objects': [],
      'directions': {},
  }

  # Put a plane on the ground so we can compute cardinal directions
  bpy.ops.mesh.primitive_plane_add(radius=5)
  plane = bpy.context.object

  def rand(L):
    return 2.0 * L * (random.random() - 0.5)

  # Randomly gitter camera from the default location
  #default_camera = default_config['camera']
  default_camera_jitters = default_config['camera_jitters']
  if args.camera_jitter > 0:
    for i in range(3):
      rand_camera_jitter = rand(args.camera_jitter)
      bpy.data.objects['Camera'].location[i] += (default_camera_jitters[i] + rand_camera_jitter)

  # Figure out the left, up, and behind directions along the plane and record
  # them in the scene structure
  camera = bpy.data.objects['Camera']
  plane_normal = plane.data.vertices[0].normal
  cam_behind = camera.matrix_world.to_quaternion() * Vector((0, 0, -1))
  cam_left = camera.matrix_world.to_quaternion() * Vector((-1, 0, 0))
  cam_up = camera.matrix_world.to_quaternion() * Vector((0, 1, 0))
  plane_behind = (cam_behind - cam_behind.project(plane_normal)).normalized()
  plane_left = (cam_left - cam_left.project(plane_normal)).normalized()
  plane_up = cam_up.project(plane_normal).normalized()

  # Delete the plane; we only used it for normals anyway. The base scene file
  # contains the actual ground plane.
  utils.delete_object(plane)

  # Save all six axis-aligned directions in the scene struct
  scene_struct['directions']['behind'] = tuple(plane_behind)
  scene_struct['directions']['front'] = tuple(-plane_behind)
  scene_struct['directions']['left'] = tuple(plane_left)
  scene_struct['directions']['right'] = tuple(-plane_left)
  scene_struct['directions']['above'] = tuple(plane_up)
  scene_struct['directions']['below'] = tuple(-plane_up)

  # Use the same lamp light jitters
  default_key_jitters = default_config['key_light_jitters']
  default_back_jitters = default_config['back_light_jitters']
  default_fill_jitters = default_config['fill_light_jitters']
  for i in range(3):
    bpy.data.objects['Lamp_Key'].location[i] += default_key_jitters[i]
  for i in range(3):
    bpy.data.objects['Lamp_Back'].location[i] += default_back_jitters[i]
  for i in range(3):
    bpy.data.objects['Lamp_Fill'].location[i] += default_fill_jitters[i]
  """
  if args.key_light_jitter > 0:
    for i in range(3):
      rand_key_light_jitter = rand(args.key_light_jitter)
      bpy.data.objects['Lamp_Key'].location[i] += rand_key_light_jitter
  if args.back_light_jitter > 0:
    for i in range(3):
      rand_back_light_jitter = rand(args.back_light_jitter)
      bpy.data.objects['Lamp_Back'].location[i] += rand_back_light_jitter
  if args.fill_light_jitter > 0:
    for i in range(3):
      rand_fill_light_jitter = rand(args.fill_light_jitter)
      bpy.data.objects['Lamp_Fill'].location[i] += rand_fill_light_jitter
  """

  # Now make some semantic changes to default objects
  default_objects = default_config['objects']
  sc_objects, sc_blend_objects, success = \
    apply_change(default_objects, scene_struct, args, camera, change_type)
  if not success:
    print('Could not semantically change the given scene for change type: %s' % change_type)
    return False

  # Render the scene and dump the scene data structure
  scene_struct['objects'] = sc_objects
  scene_struct['relationships'] = compute_all_relationships(scene_struct)
  while True:
    try:
      bpy.ops.render.render(write_still=True)
      break
    except Exception as e:
      print(e)

  with open(output_scene, 'w') as f:
    json.dump(scene_struct, f, indent=2)

  if output_blendfile is not None:
    bpy.ops.wm.save_as_mainfile(filepath=output_blendfile)

  return True


def add_random_objects(scene_struct, num_objects, args, camera):
  """
  Add random objects to the current blender scene
  """

  # Load the property file
  with open(args.properties_json, 'r') as f:
    properties = json.load(f)
    color_name_to_rgba = {}
    for name, rgb in properties['colors'].items():
      rgba = [float(c) / 255.0 for c in rgb] + [1.0]
      color_name_to_rgba[name] = rgba
    material_mapping = [(v, k) for k, v in properties['materials'].items()]
    object_mapping = [(v, k) for k, v in properties['shapes'].items()]
    size_mapping = list(properties['sizes'].items())

  shape_color_combos = None
  if args.shape_color_combos_json is not None:
    with open(args.shape_color_combos_json, 'r') as f:
      shape_color_combos = list(json.load(f).items())

  positions = []
  objects = []
  blender_objects = []
  for i in range(num_objects):
    # Choose a random size
    size_name, r = random.choice(size_mapping)

    # Try to place the object, ensuring that we don't intersect any existing
    # objects and that we are more than the desired margin away from all existing
    # objects along all cardinal directions.
    num_tries = 0
    while True:
      # If we try and fail to place an object too many times, then delete all
      # the objects in the scene and start over.
      num_tries += 1
      if num_tries > args.max_retries:
        for obj in blender_objects:
          utils.delete_object(obj)
        return add_random_objects(scene_struct, num_objects, args, camera)
      x = random.uniform(-3, 3)
      y = random.uniform(-3, 3)
      # Check to make sure the new object is further than min_dist from all
      # other objects, and further than margin along the four cardinal directions
      dists_good = True
      margins_good = True
      for (xx, yy, rr) in positions:
        dx, dy = x - xx, y - yy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist - r - rr < args.min_dist:
          dists_good = False
          break
        for direction_name in ['left', 'right', 'front', 'behind']:
          direction_vec = scene_struct['directions'][direction_name]
          assert direction_vec[2] == 0
          margin = dx * direction_vec[0] + dy * direction_vec[1]
          if 0 < margin < args.margin:
            print(margin, args.margin, direction_name)
            print('BROKEN MARGIN!')
            margins_good = False
            break
        if not margins_good:
          break

      if dists_good and margins_good:
        break

    # Choose random color and shape
    if shape_color_combos is None:
      obj_name, obj_name_out = random.choice(object_mapping)
      color_name, rgba = random.choice(list(color_name_to_rgba.items()))
    else:
      obj_name_out, color_choices = random.choice(shape_color_combos)
      color_name = random.choice(color_choices)
      obj_name = [k for k, v in object_mapping if v == obj_name_out][0]
      rgba = color_name_to_rgba[color_name]

    # For cube, adjust the size a bit
    if obj_name == 'Cube':
      r /= math.sqrt(2)

    # Choose random orientation for the object.
    theta = 360.0 * random.random()

    # Actually add the object to the scene
    utils.add_object(args.shape_dir, obj_name, r, (x, y), theta=theta)
    obj = bpy.context.object
    blender_objects.append(obj)
    positions.append((x, y, r))

    # Attach a random material
    mat_name, mat_name_out = random.choice(material_mapping)
    utils.add_material(mat_name, Color=rgba)

    # Record data about the object in the scene data structure
    pixel_coords = utils.get_camera_coords(camera, obj.location)
    objects.append({
      'shape': obj_name_out,
      'size': size_name,
      'material': mat_name_out,
      '3d_coords': tuple(obj.location),
      'rotation': theta,
      'pixel_coords': pixel_coords,
      'color': color_name,
    })

  # Check that all objects are at least partially visible in the rendered image
  all_visible = check_visibility(blender_objects, args.min_pixels_per_object)
  if not all_visible:
    # If any of the objects are fully occluded then start over; delete all
    # objects from the scene and place them all again.
    print('Some objects are occluded; replacing objects')
    for obj in blender_objects:
      utils.delete_object(obj)
    return add_random_objects(scene_struct, num_objects, args, camera)

  return objects, blender_objects


def apply_change(default_objects, scene_struct, args, camera, change_type):
  """
  Apply changes to default objects to the current blender scene.
  """

  # Load the property file
  with open(args.properties_json, 'r') as f:
    properties = json.load(f)
    color_name_to_rgba = {}
    for name, rgb in properties['colors'].items():
      rgba = [float(c) / 255.0 for c in rgb] + [1.0]
      color_name_to_rgba[name] = rgba
    material_mapping = [(v, k) for k, v in properties['materials'].items()]
    object_mapping = [(v, k) for k, v in properties['shapes'].items()]
    size_mapping = list(properties['sizes'].items())

  shape_color_combos = None
  if args.shape_color_combos_json is not None:
    with open(args.shape_color_combos_json, 'r') as f:
      shape_color_combos = list(json.load(f).items())

  def render_object(obj):
    obj_name_out = obj['shape']
    obj_name = [k for k, v in object_mapping if v == obj_name_out][0]
    color_name = obj['color']
    rgba = color_name_to_rgba[color_name]
    size_name = obj['size']
    r = [v for k, v in size_mapping if k == size_name][0]
    if obj_name == 'Cube':
      r /= math.sqrt(2)
    theta = obj['rotation']
    mat_name_out = obj['material']
    mat_name = [k for k, v in material_mapping if v == mat_name_out][0]
    x, y, z = obj['3d_coords']
    position = (x, y, r)
    utils.add_object(args.shape_dir, obj_name, r, (x, y), theta=theta)
    new_blend_obj = bpy.context.object
    utils.add_material(mat_name, Color=rgba)
    new_pixel_coords = utils.get_camera_coords(camera, new_blend_obj.location)
    return new_blend_obj, position, new_pixel_coords

  def check_dist_margin(this_position, other_positions):
    # Check to make sure the new object is further than min_dist from all
    # other objects, and further than margin along the four cardinal directions
    dists_good = True
    margins_good = True
    x, y, r = this_position
    for (xx, yy, rr) in other_positions:
      dx, dy = x - xx, y - yy
      dist = math.sqrt(dx * dx + dy * dy)
      if dist - r - rr < args.min_dist:
        dists_good = False
        break
      for direction_name in ['left', 'right', 'front', 'behind']:
        direction_vec = scene_struct['directions'][direction_name]
        assert direction_vec[2] == 0
        margin = dx * direction_vec[0] + dy * direction_vec[1]
        if 0 < margin < args.margin:
          print(margin, args.margin, direction_name)
          print('BROKEN MARGIN!')
          margins_good = False
          break
      if not margins_good:
        break

    return dists_good and margins_good

  curr_num_objects = len(default_objects)
  new_objects = []
  if change_type == 'color':
    # Randomly pick an object and change its color.
    object_idx = random.randint(0, curr_num_objects - 1)
    for i, obj in enumerate(default_objects):
      new_obj = copy.deepcopy(obj)
      if i == object_idx:
        curr_color_name = new_obj['color']
        while True:
          new_color_name, new_rgba = random.choice(list(color_name_to_rgba.items()))
          if new_color_name != curr_color_name:
            break
        new_obj['color'] = new_color_name
      new_objects.append(new_obj)
  elif change_type == 'material':
    # Randomly pick an object and change its material.
    object_idx = random.randint(0, curr_num_objects - 1)
    for i, obj in enumerate(default_objects):
      new_obj = copy.deepcopy(obj)
      if i == object_idx:
        curr_mat_name_out = new_obj['material']
        curr_mat_name = [k for k, v in material_mapping if v == curr_mat_name_out][0]
        while True:
          new_mat_name, new_mat_name_out = random.choice(material_mapping)
          if new_mat_name != curr_mat_name:
            break
        new_obj['material'] = new_mat_name_out
      new_objects.append(new_obj)
  elif change_type == 'shape':
    # Randomly pick an object and change the shape.
    pass
  elif change_type == 'drop':
    # Randomly pick an object and delete from the scene.
    object_idx = random.randint(0, curr_num_objects - 1)
    for i, obj in enumerate(default_objects):
      new_obj = copy.deepcopy(obj)
      if i == object_idx:
        continue
      else:
        new_objects.append(new_obj)
  elif change_type == 'add':
    # Randomly add an object to the scene.
    # Need to check distance and margin

    # Randomly pick size
    new_size_name, new_r = random.choice(size_mapping)

    # Try to place the object, ensuring that we don't intersect any existing
    # objects and that we are more than the desired margin away from all existing
    # objects along all cardinal directions.
    other_positions = []
    for i, obj in enumerate(default_objects):
      obj_name_out = obj['shape']
      obj_name = [k for k, v in object_mapping if v == obj_name_out][0]
      size_name = obj['size']
      r = [v for k, v in size_mapping if k == size_name][0]
      if obj_name == 'Cube':
        r /= math.sqrt(2)
      x, y, z = obj['3d_coords']
      position = (x, y, r)
      other_positions.append(position)
      new_objects.append(copy.deepcopy(obj))
    num_tries = 0
    while True:
      # If we try and fail to place an object too many times, 
      # reject the default image.
      num_tries += 1
      if num_tries > args.max_retries:
        return None, None, False
      new_x = random.uniform(-3, 3)
      new_y = random.uniform(-3, 3)
      this_position = (new_x, new_y, new_r) 
      success = check_dist_margin(this_position, other_positions)
      if success:
        break
    
    # Choose random color and shape
    if shape_color_combos is None:
      new_obj_name, new_obj_name_out = random.choice(object_mapping)
      new_color_name, new_rgba = random.choice(list(color_name_to_rgba.items()))
    else:
      new_obj_name_out, color_choices = random.choice(shape_color_combos)
      new_color_name = random.choice(color_choices)
      new_obj_name = [k for k, v in object_mapping if v == new_obj_name_out][0]
      new_rgba = color_name_to_rgba[new_color_name]

    # For cube, adjust the size a bit
    if new_obj_name == 'Cube':
      new_r /= math.sqrt(2)

    # Choose random orientation for the object.
    new_theta = 360.0 * random.random()

    # Attach a random material
    new_mat_name, new_mat_name_out = random.choice(material_mapping)

    new_objects.append({
      'shape': new_obj_name_out,
      'size': new_size_name,
      'material': new_mat_name_out,
      '3d_coords': (new_x, new_y, -1),
      'rotation': new_theta,
      'pixel_coords': None,
      'color': new_color_name,
    })

  elif change_type == 'switch':
    # Randomly pick two objects and switch locations.
    # Need to check distance and margin
    pass
  elif change_type == 'random':
    # Apply random changes from above.
    pass
  elif change_type == 'same':
    # Don't apply any change to the objects.
    for i, obj in enumerate(default_objects):
      new_obj = copy.deepcopy(obj)
      new_objects.append(new_obj)

  new_num_objects = len(new_objects)
  new_positions = []
  new_blend_objects = []
  for obj in new_objects:
    new_blend_object, new_position, new_pixel_coords = render_object(obj)
    new_blend_objects.append(new_blend_object)
    new_positions.append(new_position)
    obj['pixel_coords'] = new_pixel_coords

  # Check that all objects are at least partially visible in the rendered image
  all_visible = check_visibility(new_blend_objects, args.min_pixels_per_object)
  if not all_visible:
    # If any of the objects are fully occluded, delete all and skip this one.
    print('Some objects are occluded')
    for obj in new_blend_objects:
      utils.delete_object(obj)
    return None, None, False

  return new_objects, new_blend_objects, True


def compute_all_relationships(scene_struct, eps=0.2):
  """
  Computes relationships between all pairs of objects in the scene.
  
  Returns a dictionary mapping string relationship names to lists of lists of
  integers, where output[rel][i] gives a list of object indices that have the
  relationship rel with object i. For example if j is in output['left'][i] then
  object j is left of object i.
  """
  all_relationships = {}
  for name, direction_vec in scene_struct['directions'].items():
    if name == 'above' or name == 'below': continue
    all_relationships[name] = []
    for i, obj1 in enumerate(scene_struct['objects']):
      coords1 = obj1['3d_coords']
      related = set()
      for j, obj2 in enumerate(scene_struct['objects']):
        if obj1 == obj2: continue
        coords2 = obj2['3d_coords']
        diff = [coords2[k] - coords1[k] for k in [0, 1, 2]]
        dot = sum(diff[k] * direction_vec[k] for k in [0, 1, 2])
        if dot > eps:
          related.add(j)
      all_relationships[name].append(sorted(list(related)))
  return all_relationships


def check_visibility(blender_objects, min_pixels_per_object):
  """
  Check whether all objects in the scene have some minimum number of visible
  pixels; to accomplish this we assign random (but distinct) colors to all
  objects, and render using no lighting or shading or antialiasing; this
  ensures that each object is just a solid uniform color. We can then count
  the number of pixels of each color in the output image to check the visibility
  of each object.

  Returns True if all objects are visible and False otherwise.
  """
  f, path = tempfile.mkstemp(suffix='.png')
  object_colors = render_shadeless(blender_objects, path=path)
  img = bpy.data.images.load(path)
  p = list(img.pixels)
  color_count = Counter((p[i], p[i+1], p[i+2], p[i+3])
                        for i in range(0, len(p), 4))
  os.remove(path)
  if len(color_count) != len(blender_objects) + 1:
    return False
  for _, count in color_count.most_common():
    if count < min_pixels_per_object:
      return False
  return True


def render_shadeless(blender_objects, path='flat.png'):
  """
  Render a version of the scene with shading disabled and unique materials
  assigned to all objects, and return a set of all colors that should be in the
  rendered image. The image itself is written to path. This is used to ensure
  that all objects will be visible in the final rendered scene.
  """
  render_args = bpy.context.scene.render

  # Cache the render args we are about to clobber
  old_filepath = render_args.filepath
  old_engine = render_args.engine
  old_use_antialiasing = render_args.use_antialiasing

  # Override some render settings to have flat shading
  render_args.filepath = path
  render_args.engine = 'BLENDER_RENDER'
  render_args.use_antialiasing = False

  # Move the lights and ground to layer 2 so they don't render
  utils.set_layer(bpy.data.objects['Lamp_Key'], 2)
  utils.set_layer(bpy.data.objects['Lamp_Fill'], 2)
  utils.set_layer(bpy.data.objects['Lamp_Back'], 2)
  utils.set_layer(bpy.data.objects['Ground'], 2)

  # Add random shadeless materials to all objects
  object_colors = set()
  old_materials = []
  for i, obj in enumerate(blender_objects):
    old_materials.append(obj.data.materials[0])
    bpy.ops.material.new()
    mat = bpy.data.materials['Material']
    mat.name = 'Material_%d' % i
    while True:
      r, g, b = [random.random() for _ in range(3)]
      if (r, g, b) not in object_colors: break
    object_colors.add((r, g, b))
    mat.diffuse_color = [r, g, b]
    mat.use_shadeless = True
    obj.data.materials[0] = mat

  # Render the scene
  bpy.ops.render.render(write_still=True)

  # Undo the above; first restore the materials to objects
  for mat, obj in zip(old_materials, blender_objects):
    obj.data.materials[0] = mat

  # Move the lights and ground back to layer 0
  utils.set_layer(bpy.data.objects['Lamp_Key'], 0)
  utils.set_layer(bpy.data.objects['Lamp_Fill'], 0)
  utils.set_layer(bpy.data.objects['Lamp_Back'], 0)
  utils.set_layer(bpy.data.objects['Ground'], 0)

  # Set the render settings back to what they were
  render_args.filepath = old_filepath
  render_args.engine = old_engine
  render_args.use_antialiasing = old_use_antialiasing

  return object_colors


if __name__ == '__main__':
  if INSIDE_BLENDER:
    # Run normally
    argv = utils.extract_args()
    args = parser.parse_args(argv)
    main(args)
  elif '--help' in sys.argv or '-h' in sys.argv:
    parser.print_help()
  else:
    print('This script is intended to be called from blender like this:')
    print()
    print('blender --background --python render_images.py -- [args]')
    print()
    print('You can also run as a standalone python script to view all')
    print('arguments like this:')
    print()
    print('python render_images.py --help')
