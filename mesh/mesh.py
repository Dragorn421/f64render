from dataclasses import dataclass

import numpy as np
import bpy
import bmesh
import time
import gpu
from ..material.parser import F64Material

# Container for all vertex attributes
@dataclass
class MeshBuffers:
  # input buffers:
    vert: np.ndarray
    color: np.ndarray
    uv: np.ndarray
    norm: np.ndarray
    indices: np.ndarray # global index array, sorted by material
    index_offsets: np.ndarray # offsets for each material in the index array
  # render data:
    batch: gpu.types.GPUBatch
    cc_data: list[np.ndarray]
    cc_conf: list[np.ndarray]
    ubo_cc_data: list[gpu.types.GPUUniformBuf]
    ubo_cc_conf: list[gpu.types.GPUUniformBuf]
    material: F64Material = None
    mesh_name: str = "" # multiple obj. can share the same mesh, store to allow deletion by name

# Converts a blender mesh into buffers to be used by the GPU renderer
# Note that this can be a slow process, so it should be cached externally
# This will only handle mesh data itself, materials are not read out here
def mesh_to_buffers(mesh: bpy.types.Mesh) -> MeshBuffers:
  tDes = time.process_time()
  mesh.calc_loop_triangles()

  # Here we want to transform all attributes into un-indexed arrays of per-vertex data
  # Position + normals are stored per vertex (indexed), colors and uvs are stored per face-corner
  # All need to be normalized to the same length
  
  color_layer = mesh.color_attributes.get("Col")
  alpha_layer = mesh.color_attributes.get("Alpha")
  uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None

  num_corners = len(mesh.loop_triangles) * 3
  # print("Faces: ", num_corners, color_layer)

  positions = np.empty((num_corners, 3), dtype=np.float32)
  normals   = np.empty((num_corners, 3), dtype=np.float32)
  colors    = np.empty((num_corners, 4), dtype=np.float32)
  uvs       = np.empty((num_corners, 2), dtype=np.float32)

  indices   = np.empty((num_corners   ), dtype=np.int32)
  mesh.loop_triangles.foreach_get('vertices', indices)

  # map vertices to unique face-corner
  tmp_vec3 = np.empty((len(mesh.vertices), 3), dtype=np.float32)
  mesh.vertices.foreach_get('co', tmp_vec3.ravel())
  positions = tmp_vec3[indices]

  # determine if smooth shading is used
  use_flat = np.empty(len(mesh.loop_triangles), dtype=np.int8)
  mesh.loop_triangles.foreach_get('use_smooth', use_flat)
  use_smooth = use_flat.repeat(3)
  use_flat = 1 - use_flat

  # fetch and mask smooth normals
  mesh.vertices.foreach_get('normal', tmp_vec3.ravel())
  normals = tmp_vec3[indices]
  normals *= use_smooth[:,np.newaxis] # mask out

  # fetch and merge flat-shaded normals
  tmp_vec3_norm = np.empty((len(mesh.loop_triangles), 3), dtype=np.float32)
  mesh.loop_triangles.foreach_get('normal', tmp_vec3_norm.ravel())
  tmp_vec3_norm *= use_flat[:,np.newaxis] # mask out
  normals += np.repeat(tmp_vec3_norm, 3, axis=0)

  mesh.loop_triangles.foreach_get('loops', indices)
  
  if uv_layer: 
    uv_layer.foreach_get('uv', uvs.ravel())
    uvs = uvs[indices]
  else:
    uvs.fill(0.0)

  if color_layer:
    colors_tmp = np.empty((len(color_layer.data), 4), dtype=np.float32)
    color_layer.data.foreach_get('color_srgb', colors_tmp.ravel())
    colors = colors_tmp[indices]

    if alpha_layer:
      alpha_layer.data.foreach_get('color', colors_tmp.ravel())
      colors[:, 3] = colors_tmp[indices, 0]

  else:
    colors.fill(1.0)
  
  # create index buffers for the mesh by material, the data behind it is unindexed
  # this is done to do a cheap split by material
  mesh.loop_triangles.foreach_get('material_index', use_flat) # materials, e.g.: [0, 1, 0, 1, 2, 1, ...]
  index_array = np.arange(num_corners, dtype=np.int32) # -> [0, 1, 2, 3, 4, 5, ...]
  index_array = index_array.reshape((-1, 3))           # -> [[0, 1, 2], [3, 4, 5], ...]
  
  index_array = index_array[np.argsort(use_flat)] # sort index_array by value in use_flat (aka material-index)
  index_offsets = np.bincount(use_flat)           # now get counts of each material, e.g.: [1, 2] where index is material-index
  index_offsets = np.insert(index_offsets, 0, 0)  # prepend 0 to turn counts into offsets
  index_offsets = np.cumsum(index_offsets) * 3    # converted into accumulated offset / mul. by 3 for triangles

  print(" - Mesh", (time.process_time() - tDes) * 1000)

  return MeshBuffers(positions, colors, uvs, normals, index_array, index_offsets, None, None, None, None, None)