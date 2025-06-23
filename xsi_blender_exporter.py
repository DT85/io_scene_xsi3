import bpy
from mathutils import Euler, Matrix, Vector
from math import radians, degrees
    
from . import blend2xsi

# Normals changed in 4.1 from 4.0
OLD_NORMALS = not (bpy.app.version[0] >= 4 and bpy.app.version[1] >= 1)

USE_FRAME_NAME_AS_MESH_NAME = True
ALLOW_MESH_WITH_NO_FACES = False
ALLOW_MESH_WITH_NO_MATERIAL = False
ALLOW_ROOT_LEVEL_ANIMS = True

KEYFRAME_PATHS = {"location", "rotation_euler", "rotation_quaternion", "scale"}
ALLOWED_SUB_OBJECTS = {"MESH", "EMPTY", "ARMATURE"}

DEFAULT_MATERIAL = {
	"diffuse": (blend2xsi.DEFAULT_DIFFUSE, tuple),
	"hardness": (blend2xsi.DEFAULT_HARDNESS, float),
	"specular": (blend2xsi.DEFAULT_SPECULAR, tuple),
	"ambient": (blend2xsi.DEFAULT_AMBIENT, tuple),
	"emissive": (blend2xsi.DEFAULT_EMISSIVE, tuple),
	"shading_type": (blend2xsi.DEFAULT_SHADING_TYPE, int),
	"texture": (None, str)
}

# Mesh for hardpoint objects
def generate_pointer_mesh(scale=0.05):
	bz2mesh = blend2xsi.Mesh()
	
	bz2mesh.vertices = (
		(-scale, -scale, 0.0),
		(scale, -scale, 0.0),
		(-scale, scale, 0.0),
		(scale, scale, 0.0),
		(0.0, 0.0, 7.0 * scale)
	)
	
	bz2mesh.normal_vertices = bz2mesh.vertices
	bz2mesh.faces = ((0, 2, 3, 1), (3, 2, 4), (0, 1, 4), (1, 3, 4), (2, 0, 4))
	bz2mesh.normal_faces = bz2mesh.faces
	bz2mesh.face_materials = [blend2xsi.Material(diffuse=(1.0, 1.0, 1.0))] * len(bz2mesh.faces)
	
	return bz2mesh

def generate_bone_mesh(bone, posebone):
	radius = bone.length*0.125
	base = bone.length*0.20
	tip = bone.length
	
	rgb = tuple(posebone.bone_group.colors.active)[0:3] if posebone.bone_group else blend2xsi.DEFAULT_DIFFUSE[0:3]
	rgba = rgb + (0.80,)
	
	bz2mesh = blend2xsi.Mesh()
	
	bz2mesh.vertices = (
		(-radius, base, -radius),
		(0.0, 0.0, 0.0),
		(radius, base, -radius),
		(-radius, base, radius),
		(radius, base, radius),
		(0.0, tip, 0.0)
	)
	
	bz2mesh.faces = (
		(2, 4, 1),
		(1, 3, 0),
		(1, 4, 3),
		(2, 1, 0),
		(5, 3, 4),
		(5, 2, 0),
		(5, 0, 3),
		(5, 4, 2)
	)
	
	bz2mesh.face_materials = [blend2xsi.Material(diffuse=rgba)] * len(bz2mesh.faces)
	
	bz2mesh.normal_vertices = (
		(0.8, -0.6, 0),
		(0.8, -0.6, 0),
		(0.8, -0.6, 0),
		(-0.8, -0.6, 0),
		(-0.8, -0.6, 0),
		(-0.8, -0.6, 0),
		(0, -0.6, 0.8),
		(0, -0.6, 0.8),
		(0, -0.6, 0.8),
		(0, -0.6, -0.8),
		(0, -0.6, -0.8),
		(0, -0.6, -0.8),
		(0, 0.184289, 0.982872),
		(0, 0.184289, 0.982872),
		(0, 0.184289, 0.982872),
		(0, 0.184289, -0.982872),
		(0, 0.184289, -0.982872),
		(0, 0.184289, -0.982872),
		(-0.982872, 0.184289, 0),
		(-0.982872, 0.184289, 0),
		(-0.982872, 0.184289, 0),
		(0.982872, 0.184289, 0),
		(0.982872, 0.184289, 0),
		(0.982872, 0.184289, 0)
	)
	
	bz2mesh.normal_faces = (
		(0, 1, 2),
		(3, 4, 5),
		(6, 7, 8),
		(9, 10, 11),
		(12, 13, 14),
		(15, 16, 17),
		(18, 19, 20),
		(21, 22, 23)
	)
	
	return bz2mesh

def get_keyframes_filtered(action, keyframe_filter):
	filtered_points = {key: [] for key in keyframe_filter}
	key_start, key_end = tuple(action.frame_range)
	
	for fcurve in action.fcurves:
		if not fcurve.data_path in keyframe_filter:
			continue
		
		for point in fcurve.keyframe_points:
			pos = int(point.co[0])
			
			if point.co[0] in filtered_points[fcurve.data_path]:
				continue
			
			if pos >= key_start and pos <= key_end:
				filtered_points[fcurve.data_path].append(point)
	
	return filtered_points

# Returns dictionary of {Bone Name: [(Vert Index, Vert Weight)...]}
def get_vertex_weights(obj, group_names=None):
	vertex_weights = {}
	name_by_index = {}
	indices_used = []
	
	for vertex_group in obj.vertex_groups:
		if group_names == None or vertex_group.name in group_names:
			name_by_index[vertex_group.index] = vertex_group.name
			vertex_weights[vertex_group.name] = []
			indices_used.append(vertex_group.index)
	
	for vertex in obj.data.vertices:
		for group in vertex.groups:
			if group.group in indices_used:
				name = name_by_index[group.group]
				vertex_weights[name].append((vertex.index, group.weight * 100.0))
	
	return vertex_weights

def get_armature(bpy_obj):
	armature_mod = None
	for modifier in bpy_obj.modifiers:
		if modifier.type == "ARMATURE":
			if not armature_mod:
				armature_mod = modifier.object
			else:
				print("XSI Warning: Multiple armature modifiers may cause unexpected results.")
				break
	
	return armature_mod

def obj_hierarchy_to_linear(bpy_objects):
	for bpy_obj in bpy_objects:
		for bpy_subobj in bpy_obj.children:
			if bpy_subobj.type in ALLOWED_SUB_OBJECTS:
				yield bpy_subobj
			
			yield from obj_hierarchy_to_linear([bpy_subobj])

class Save:
	def __init__(self, operator, context, filepath="", **opt):
		self.depsgraph = context.evaluated_depsgraph_get()
		self.blend2xsi_xsi = blend2xsi.XSI()
		self.opt = opt
		
		original_keyframe_position = bpy.context.scene.frame_current
		
		#if opt["export_animations"] and original_keyframe_position != bpy.context.scene.frame_start:
		#	# This is so animated objects keyframe offset does not affect object's unanimated pose or matrix.
		#	# We'll set it back to original_keyframe_position later when we're done.
		#	bpy.context.scene.frame_set(bpy.context.scene.frame_start)
		
		if opt["export_mode"] == "ACTIVE_COLLECTION":
			objects = [obj for obj in bpy.context.view_layer.active_layer_collection.collection.objects if (obj.parent == None and not obj.hide_viewport)]
		
		elif opt["export_mode"] == "SELECTED_OBJECTS":
			objects = [obj for obj in bpy.data.objects if obj.select_get()]
		
		if len(objects) >= 2:
			print("XSI Warning: BZ2 does not support more than 1 root-level object:", ", ".join(obj.name for obj in objects))

		self.referenced_objects = objects + list(obj_hierarchy_to_linear(objects))
		self.enveloped_bz2frames = {}
		self.bone_name_to_bz2frame = {}
		
		for obj in objects:
			if obj.type in ALLOWED_SUB_OBJECTS:
				self.blend2xsi_xsi.frames += [self.object_to_bz2frame(obj, is_root_level=True)]
		
		# Envelopes for bones
		if opt["export_envelopes"]:
			for bz2frame, obj in self.enveloped_bz2frames.items():
				vertex_weights = get_vertex_weights(obj.evaluated_get(self.depsgraph), self.bone_name_to_bz2frame)
				
				for bone_name, bz2bone in self.bone_name_to_bz2frame.items():
					if bone_name in vertex_weights:
						bz2frame.envelopes.append(blend2xsi.Envelope(bz2bone, vertex_weights[bone_name]))
					else:
						print("XSI Warning: Vertex group not found for bone:", bone_name)
		
		# Set keyframe position back, if changed during reading animation keyframes
		if bpy.context.scene.frame_current != original_keyframe_position:
			bpy.context.scene.frame_set(original_keyframe_position)
	
	def material_to_bz2material(self, material):
		mat = {}
		
		# Check material's custom attributes, these can be used to explicitly override material settings
		for key in DEFAULT_MATERIAL:
			default, value_type = DEFAULT_MATERIAL[key]
			if key in material: # if 'key' is in custom attributes of 'blender material object'
				mat[key] = value_type(material[key])
				# print("Using custom property %r with %r for material %r." % (key, mat[key], material.name))
			else:
				mat[key] = default
		
		# Use the first texture in the node tree if applicable.
		if material.use_nodes and not mat["texture"]:
			for node in material.node_tree.nodes:
				if node.type == "TEX_IMAGE":
					mat["texture"] = node.image.filepath
					break # Found an image texture.
		
		return blend2xsi.Material(
			mat["diffuse"],
			mat["hardness"],
			mat["specular"],
			mat["ambient"],
			mat["emissive"],
			mat["shading_type"],
			mat["texture"]
		)

	def matrix_to_bz2matrix(self, local_matrix):
		return blend2xsi.Matrix(*list(tuple(row) for row in tuple(local_matrix.transposed())))

	def matrix_to_xsi(self, matrix):
		# create the rotation matrix
		#mat_rot90 = Matrix.Rotation(pi / 2, 4, 'X')
		
		# create the inverse rotation matrix from the rotation matrix
		#mat_rot90_inv = mat_rot90.inverted_safe()
		
		# transpose these matrices
		#mat_rot90.transpose()
		#mat_rot90_inv.transpose()
		#matrix.transpose()
		
		# perform coordinate system transformation
		#matrix = mat_rot90 @ matrix @ mat_rot90_inv
		
		# non-multiplication version. invert the Y, and swap the Y & Z
		row_y = -matrix.row[1].copy()
		row_z = matrix.row[2].copy()
		matrix.row[1] = row_z
		matrix.row[2] = row_y
		
		col_y = -matrix.col[1].copy()
		col_z = matrix.col[2].copy()
		matrix.col[1] = col_z
		matrix.col[2] = col_y

	def bone_mat_rot_Y_to_X(self, matrix):
		# roll by 90 degrees
		matrix[0][0], matrix[1][0], matrix[2][0], matrix[0][2], matrix[1][2], matrix[2][2] = matrix[0][2], matrix[1][2], matrix[2][2], - \
			matrix[0][0], -matrix[1][0], -matrix[2][0]
		
		# swap the columns
		col_x = matrix.col[1].copy()
		col_y = -matrix.col[0].copy()
		matrix.col[0] = col_x
		matrix.col[1] = col_y
		
		# swap the positions
		matrix[3][0], matrix[3][1] = matrix[3][1], -matrix[3][0]
	
	def object_to_bz2frame(self, obj, is_root_level=False):
		bz2frame = blend2xsi.Frame(obj.name)
		bz2frame.mesh = None
		is_skinned = self.opt["export_envelopes"] and get_armature(obj) in self.referenced_objects

		# zero out the vectors for the scene root (usually 'model_root') object(s)
		if is_root_level and self.opt["zero_root_transforms"]:
			# send the vectors to 'bz2xsi.py' for writing...
			bz2frame.srt_sca = Vector((1.0, 1.0, 1.0))
			bz2frame.srt_rot = Vector((0.0, 0.0, 0.0))
			bz2frame.srt_pos = Vector((0.0, 0.0, 0.0))
		else:
			mat_transform = Matrix(obj.matrix_local)
			
			# change the 'front' from Y+ to X+
			self.bone_mat_rot_Y_to_X(mat_transform)
			
			if obj.parent:
				mat_transform_parent = Matrix(obj.parent.matrix_local)
				
				# change the 'front' from Y+ to X+
				self.bone_mat_rot_Y_to_X(mat_transform_parent)
				
				mat_transform = mat_transform_parent.inverted_safe() @ mat_transform
			
			# zero out the vectors for the mesh_root/skeleton_root objects
			if obj.name == "mesh_root" or obj.name == "skeleton_root":
				# send the vectors to 'blend2xsi.py' for writing...
				bz2frame.srt_sca = Vector((1.0, 1.0, 1.0))
				bz2frame.srt_rot = Vector((0.0, 0.0, 0.0))
				bz2frame.srt_pos = Vector((0.0, 0.0, 0.0))
			else:
				# convert the matrix to xsi
				self.matrix_to_xsi(mat_transform)
				
				sca = Vector(mat_transform.to_scale())
				deg = Vector([degrees(n) for n in mat_transform.to_euler()])
				pos = Vector(mat_transform.to_translation())
				
				# send the vectors to 'blend2xsi.py' for writing...
				bz2frame.srt_sca = sca
				bz2frame.srt_rot = deg
				bz2frame.srt_pos = pos
			
		if is_skinned:
			mat_basepose = Matrix(obj.matrix_local)
			
			# convert the matrix to xsi
			self.matrix_to_xsi(mat_basepose)
			
			sca = Vector(mat_basepose.to_scale())
			deg = Vector([degrees(n) for n in mat_basepose.to_euler()])
			pos = Vector(mat_basepose.to_translation())
			
			# send the vectors to 'blend2xsi.py' for writing...
			bz2frame.basepose_sca = sca
			bz2frame.basepose_rot = deg
			bz2frame.basepose_pos = pos
		
		obj_eval = obj.evaluated_get(self.depsgraph)
		data = obj_eval.data
		
		scale = obj_eval.matrix_local.to_scale()
		if scale != Vector((1.0, 1.0, 1.0)):
			print("XSI Warning: Scaling information %r contained in object %r is not supported by BZ2." % (scale, obj.name))
		
		if obj.type == "MESH" and not len(data.vertices) <= 0:
			if not ALLOW_MESH_WITH_NO_FACES and len(data.polygons) <= 0:
				print("XSI Warning: Mesh for object %r has no faces, ignoring mesh data." % obj.name)
			
			else:
				if self.opt["export_mesh"]:
					bz2frame.mesh = self.mesh_to_bz2mesh(data, bz2frame.name if USE_FRAME_NAME_AS_MESH_NAME else None)
					
					if is_skinned:
                        # ensure the we're setting the skin weights at frame 0.
						bpy.context.scene.frame_set(bpy.context.scene.frame_start)
						
						self.enveloped_bz2frames[bz2frame] = obj_eval
		
		elif obj.type == "ARMATURE":
			for bone, posebone in zip(obj_eval.data.bones, obj_eval.pose.bones):
				if not bone.parent:
					bz2frame.frames += [self.bone_to_bz2frame(obj, bone, posebone, obj_eval)]
		
		# All other supported blender types are treated as empty objects by default below.
		elif self.opt["generate_empty_mesh"]:
			bz2frame.mesh = generate_pointer_mesh()
			bz2frame.mesh.name = bz2frame.name
		
		if self.opt["export_animations"] and obj_eval.animation_data and obj_eval.animation_data.action:
			bz2_animations = list(self.animation_to_bz2anim(obj_eval))
			
			if is_root_level and not ALLOW_ROOT_LEVEL_ANIMS:
				bz2_animations = []
			
			if bz2_animations:
				if is_root_level:
					print("XSI Warning: Root-level object %r animation data may not behave as expected in BZ2." % obj.name)
				
				bz2frame.animation_keys += list(self.animation_to_bz2anim(obj_eval))
		
		for obj in obj.children:
			if obj.type in ALLOWED_SUB_OBJECTS:
				bz2frame.frames += [self.object_to_bz2frame(obj)]
		
		return bz2frame
	
	def animation_to_bz2anim(self, obj):
		filtered_keyframe_points = get_keyframes_filtered(obj.animation_data.action, KEYFRAME_PATHS)
		
		# Convert the filtered keyframe points to bz2 keyframe animations
		for key_type, points in filtered_keyframe_points.items():
			bz2_keyframe_type = 2 if key_type == "location" else 0
			
			if not points:
				continue
			
			bz2anim = blend2xsi.AnimationKey(bz2_keyframe_type)
			
			for point in points:
				#~ bpy.context.scene.frame_set(point.co[0])
				pos = int(point.co[0])
				bpy.context.scene.frame_set(pos)
				
				if bz2_keyframe_type == 2:
					bz2anim.add_key(pos, tuple(Matrix(obj.matrix_local).to_translation()))
				elif bz2_keyframe_type == 0:
					bz2anim.add_key(pos, tuple(Matrix(obj.matrix_local).transposed().to_quaternion()))

			yield bz2anim
	
	def bone_to_bz2frame(self, obj, bone, posebone, armature):
		bz2frame = blend2xsi.Frame(bone.name)
		bz2frame.is_bone = True
		self.bone_name_to_bz2frame[bone.name] = bz2frame		
		
		# SI_Transform SRT.
		# root bones are given in world coordinates. the rest of the bones'
		# positions are given relative to the parent
		if bone.parent is not None:
			matrix_local_parent = Matrix()
			matrix_local_parent @= Matrix(bone.parent.matrix_local)
			
			matrix_local = Matrix()
			matrix_local @= Matrix(bone.matrix_local)
			
			# change the 'front' from Y+ to X+
			self.bone_mat_rot_Y_to_X(matrix_local_parent)
			self.bone_mat_rot_Y_to_X(matrix_local)
			
			mat_srt = matrix_local_parent.inverted() @ matrix_local
		else:
			matrix_local = Matrix()
			matrix_local @= Matrix(bone.matrix_local)
			
			# change the 'front' from Y+ to X+
			self.bone_mat_rot_Y_to_X(matrix_local)
			
			mat_srt = matrix_local
		
		# convert the matrix to xsi
		self.matrix_to_xsi(mat_srt)
		
		sca = Vector(mat_srt.to_scale())
		deg = Vector([degrees(n) for n in mat_srt.to_euler()])
		pos = Vector(mat_srt.to_translation())
		
		# send the vectors to 'blend2xsi.py' for writing...
		bz2frame.srt_sca = sca
		bz2frame.srt_rot = deg
		bz2frame.srt_pos = pos
		
        # SI_Transform BASEPOSE.
		matrix_local = Matrix()
		matrix_local @= Matrix(bone.matrix_local)
		
		# change the 'front' from Y+ to X+
		self.bone_mat_rot_Y_to_X(matrix_local)
		
		mat_basepose = matrix_local
		
		# convert the matrix to xsi
		self.matrix_to_xsi(mat_basepose)
        
		bp_sca = Vector(mat_basepose.to_scale())
		bp_deg = Vector([degrees(n) for n in mat_basepose.to_euler()])
		bp_pos = Vector(mat_basepose.to_translation())
		
		# send the vectors to 'blend2xsi.py' for writing...
		bz2frame.basepose_sca = bp_sca
		bz2frame.basepose_rot = bp_deg
		bz2frame.basepose_pos = bp_pos
		
		for child_bone, child_posebone in zip(bone.children, posebone.children):
			bz2frame.frames += [self.bone_to_bz2frame(obj, child_bone, child_posebone, armature)]
		
		if self.opt["generate_bone_mesh"]:
			bz2frame.mesh = generate_bone_mesh(bone, posebone)
			bz2frame.mesh.name = bone.name
		
		if self.opt["export_animations"]:
			if armature.animation_data and armature.animation_data.action:
				bz2frame.animation_keys += list(self.bone_animation_to_bz2anim(bone, posebone, armature))
		
		return bz2frame

	def transform_to_bz2transform(self, matrix):
		bz2transform = blend2xsi.Transform()
		
        # transpose
		matrix = matrix.transposed()
		
		#loc, rot, sca = matrix.decompose()
		
        # matrix euler to degrees
		euler_degrees = matrix.to_euler()
		euler_degrees = [degrees(n) for n in euler_degrees]
		
		bz2transform.add_vector(tuple(matrix.to_scale()))
		bz2transform.add_vector(tuple(euler_degrees))
		bz2transform.add_vector(tuple(matrix.to_translation()))
		
		yield bz2transform
	
	def bone_animation_to_bz2anim(self, bone, posebone, armature):
		# fcurves will be in the armature object, not in the bone object.
		keyframe_filter = ["pose.bones[\"%s\"].%s" % (bone.name, path) for path in KEYFRAME_PATHS]
		filtered_keyframe_points = get_keyframes_filtered(armature.animation_data.action, keyframe_filter)
		
		# Convert the filtered keyframe points to bz2 keyframe animations
		location_path_name = "pose.bones[\"%s\"].location" % bone.name
		scale_path_name = "pose.bones[\"%s\"].scale" % bone.name
		
		for key_type, points in filtered_keyframe_points.items():
			if key_type == scale_path_name:
				bz2_keyframe_type = 1
			elif key_type == location_path_name:
				bz2_keyframe_type = 2
			else:
				if self.opt["export_euler"]:
					bz2_keyframe_type = 3
				else:
					bz2_keyframe_type = 0
			
			if not points:
				continue
			
			bz2anim = blend2xsi.AnimationKey(bz2_keyframe_type)
			
			# The original code here outputs animation keys 2-4 times,
			# which bloats the .XSI file, and takes longer to export.
			# Using the scene's frame range instead.
			#for point in points:
				#~ bpy.context.scene.frame_set(point.co[0])
				#pos = int(point.co[0])
			for pos in range(bpy.context.scene.frame_start,bpy.context.scene.frame_end + 1):
				bpy.context.scene.frame_set(pos)
				
				if posebone.parent:
					matrix = Matrix(posebone.parent.matrix).inverted_safe()
					matrix @= Matrix(posebone.matrix)
				else:
					matrix = Matrix(posebone.matrix)
				
				matrix = self.matrix_to_xsi(matrix)
				
				if bz2_keyframe_type == 0:
					bz2anim.add_key(pos, tuple(matrix.transposed().to_quaternion()))
				
				elif bz2_keyframe_type == 1:
					bz2anim.add_key(pos, tuple(matrix.to_scale()))
				
				elif bz2_keyframe_type == 2:
					bz2anim.add_key(pos, tuple(matrix.to_translation()))
				
				elif bz2_keyframe_type == 3:
                    # matrix euler to degrees
					mat_euler_to_degrees = matrix.to_euler()
					mat_euler_to_degrees = [degrees(n) for n in mat_euler_to_degrees]
					
					bz2anim.add_key(pos, tuple(mat_euler_to_degrees))

			yield bz2anim
	
	def mesh_to_bz2mesh(self, data, name=None):
		bz2mesh = blend2xsi.Mesh(name if name else data.name)
		if OLD_NORMALS:
			data.calc_normals_split()
		bz2materials = []
		
		if self.opt["export_mesh_materials"]:
			for material in data.materials:
				bz2materials += [self.material_to_bz2material(material)]
		
		for vertex in data.vertices:
			#if self.opt["export_jedi"]:
			tempZ = vertex.co.y * -1
			vertex.co.y = vertex.co.z
			vertex.co.z = tempZ
			
			bz2mesh.vertices += [tuple(vertex.co.xyz)]				
                
		
		for polygon in data.polygons:
			bz2mesh.faces += [tuple(polygon.vertices)]
		
		if bz2materials:
			for polygon in data.polygons:
				bz2mesh.face_materials += [bz2materials[polygon.material_index]]
		
		elif not ALLOW_MESH_WITH_NO_MATERIAL:
			print("XSI Warning: Mesh %r has no materials, adding default material." % name)
			bz2mesh.face_materials = [blend2xsi.Material()] # Default material
		
		active_uv_layer = data.uv_layers.active
		uv_layer = active_uv_layer.data if active_uv_layer else None
		active_color_layer = data.vertex_colors.active
		color_layer = active_color_layer.data if active_color_layer else None
		
		# Normals and mesh loop faces (loop indices shared for uv and vert colors)
		for polygon in data.polygons:
			for loop_index in polygon.loop_indices:
				bz2mesh.normal_vertices += [tuple(data.loops[loop_index].normal)]
			
			bz2mesh.normal_faces += [tuple(polygon.loop_indices)]
		
		if uv_layer and self.opt["export_mesh_uvmap"]:
			for poly in data.polygons:
				for loop_index in poly.loop_indices:
					bz2mesh.uv_vertices += [tuple(uv_layer[loop_index].uv)]
			
			bz2mesh.uv_faces = bz2mesh.normal_faces
		
		if color_layer and self.opt["export_mesh_vertcolor"]:
			for poly in data.polygons:
				for loop_index in poly.loop_indices:
					bz2mesh.vertex_colors += [tuple(color_layer[loop_index].color)]
			
			bz2mesh.vertex_color_faces = bz2mesh.normal_faces
		
		return bz2mesh

def save(operator, context, filepath="", **opt):
	Save(operator, context, filepath=filepath, **opt).blend2xsi_xsi.write(filepath=filepath)
	return {"FINISHED"}
