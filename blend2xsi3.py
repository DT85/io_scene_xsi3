"""This module provides Blender to XSI utilities, including a writer for XSI 3.0 files."""
VERSION = 1.0

# No print calls will be made by the module if this is False
ALLOW_PRINT = True

DEFAULT_DIFFUSE = (0.7, 0.7, 0.7, 1.0)
DEFAULT_SPECULAR = (0.35, 0.35, 0.35)
DEFAULT_EMISSIVE = (0.0, 0.0, 0.0)
DEFAULT_AMBIENT = (0.5, 0.5, 0.5)
DEFAULT_HARDNESS = 200.0
DEFAULT_SHADING_TYPE = 2
DEFAULT_TEXTURE = None

DEFAULT_XSI_NAME = "<XSI ROOT>"

RENAME_DUPLICATE_NAMED_FRAMES = True
DUPLICATE_FRAME_NOEXCEPT = False

import bpy
from datetime import datetime

class DuplicateFrame(Exception): pass

# XSI & Frame inherit from this internal class
class _FrameContainer:
	def __init__(self):
		self.xsi = self
		self.frames = []
	
	def add_frame(self, name):
		if name in self.xsi.frame_table and not DUPLICATE_FRAME_NOEXCEPT:
			raise DuplicateFrame("Duplicate Frame %r" % name)
		
		frame = Frame(name)
		frame.parent = self if not self is self.xsi else None # XSI container itself is not a parent
		frame.xsi = self.xsi
		
		self.xsi.frame_table[name] = frame
		self.frames.append(frame)
		
		return frame
	
	def get_all_frames(self):
		frames = []
		for frame in self.frames:
			yield frame
			yield from frame.get_all_frames()
	
	def find_frame(self, name):
		for frame in self.get_all_frames():
			if frame.name == name:
				return frame
	
	def get_animated_frames(self):
		for frame in self.get_all_frames():
			if frame.animation_keys:
				yield frame
	
	def get_skinned_frames(self):
		for frame in self.get_all_frames():
			if frame.envelopes:
				yield frame
	
	def get_bone_frames(self):
		for frame in self.get_all_frames():
			if frame.is_bone:
				yield frame
	
	def get_all_meshes(self):
		for frame in self.get_all_frames():
			if frame.mesh:
				yield frame.mesh
	
	def get_envelope_count(self):
		"""Returns total amount of envelopes in each frame."""
		return sum((len(f.envelopes) for f in self.get_skinned_frames()))

class XSI(_FrameContainer):
	def __init__(self, filepath=None):
		self.frame_table = {}
		self.lights = []
		self.cameras = []
		self.frames = []
		self.xsi = self
		
		self.name = filepath if filepath else DEFAULT_XSI_NAME
		
		if filepath:
			self.read(filepath)
	
	def write(self, filepath):
		with open(filepath, "w") as f:
			Writer(self, f)
	
	def is_skinned(self):
		return len(list(self.get_skinned_frames())) >= 1
	
	def is_animated(self):
		return len(list(self.get_animated_frames())) >= 1
	
	# String representation will result in XML output
	def __str__(self):
		return "%s<XSI>%s%s</XSI>" % (
			"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\" ?>\n",
			"".join(map(str, self.lights)),
			"".join(map(str, self.frames)),
		)

class PointLight:
	def __init__(self, name, rgb=None, location_xyz=None):
		self.name = name
		self.rgb = rgb if rgb else (1.0, 1.0, 1.0)
		
		if not location_xyz:
			location_xyz = (0.0, 0.0, 0.0)
		
		self.transform = Matrix(posit=(*location_xyz, 1.0))
	
	def __str__(self):
		return "<PointLight>%s (%f, %f, %f)</PointLight>" % (self.name, *self.rgb)

class Camera:
	def __init__(self, name, location_xyz=None, look_at_xyz=None, roll=0.0, near_plane=0.001, far_plane=1000.0):
		self.name = name
		self.roll = roll
		self.near_plane = near_plane
		self.far_plane = far_plane
		
		if not location_xyz:
			location_xyz = (0.0, 0.0, 0.0)
		
		if not look_at_xyz:
			look_at_xyz = (0.0, 0.0, 0.0)
		
		self.transform = Matrix(posit=(*location_xyz, 1.0))
		self.target = Matrix(posit=(*look_at_xyz, 1.0))
	
	def __str__(self):
		return "<Camera>%s</Camera>" % self.name

class Frame(_FrameContainer):
	def __init__(self, name):
		self.name = name
		self.is_bone = False
		
		self.basepose_sca_xyz = None
		self.basepose_rot_xyz = None
		self.basepose_pos_xyz = None		
		self.srt_sca_xyz = None
		self.srt_rot_xyz = None
		self.srt_pos_xyz = None
		self.pose = None
		self.mesh = None
		
		self.parent = None
		self.frames = []
		self.animation_keys = []
		
		# About envelopes:
		# Frames (meshes) which are NOT bones contain envelopes.
		# Frames which ARE bones do NOT contain envelopes, but are referenced BY envelopes.
		self.envelopes = []
	
	def __str__(self):
		return "<Frame>%s%s%s%s%s%s%s%s%s%s%s%s</Frame>" % (
			self.name,
			str(self.basepose_sca_xyz),
			str(self.basepose_rot_xyz),
			str(self.basepose_pos_xyz),
			str(self.srt_sca_xyz),
			str(self.srt_rot_xyz),
			str(self.srt_pos_xyz),
			str(self.pose),
			str(self.mesh),
			"".join(map(str, self.frames)),
			"".join(map(str, self.animation_keys)),
			"".join(map(str, self.envelopes)),
		)
	
	def get_animation_frame_range(self):
		start = end = None
		for animkey in self.animation_keys:
			for keyframe, vector in animkey.keys:
				if start == None or keyframe < start:
					start = keyframe
				if end == None or keyframe > end:
					end = keyframe
		return start, end
	
	def get_chained_name(self, delimiter=" -> "):
		frm, chain = self, []
		
		while frm:
			chain += [frm.name]
			frm = frm.parent
		
		return delimiter.join(reversed(chain))
	
	def add_animationkey(self, *args):
		self.animation_keys.append(AnimationKey(*args))
		return self.animation_keys[-1]
	
	def add_envelope(self, *args):
		self.envelopes.append(Envelope(*args))
		return self.envelopes[-1]

class Matrix:
	def __init__(self, right=None, up=None, front=None, posit=None):
		self.right = right #if right else (1.0, 0.0, 0.0, 0.0)
		self.up    = up    #if up    else (0.0, 1.0, 0.0, 0.0)
		self.front = front #if front else (0.0, 0.0, 1.0, 0.0)
		self.posit = posit #if posit else (0.0, 0.0, 0.0, 1.0)
	
	def __str__(self):
		return "<Matrix>(x=%f y=%f z=%f)</Matrix>" % tuple(self.posit[0:3])
	
	def to_list(self):
		return [list(self.right), list(self.up), list(self.front), list(self.posit)]

class Mesh:
	def __init__(self, name=None):
		self.name=name
		
		self.vertices = []
		self.faces = []
		
		self.normal_vertices = []
		self.normal_faces = []
		
		self.uv_vertices = []
		self.uv_faces = []
		
		self.face_materials = []
		
		self.vertex_colors = []
		self.vertex_color_faces = []
	
	def __str__(self):
		def XML(name, vertices, faces):
			if vertices or faces:
				return "<%s>%d Vertices %d Faces</%s>" % (
					name,
					len(vertices),
					len(faces),
					name
				)
			else:
				return ""
		
		indices, materials = self.get_material_indices()
		
		return "<Mesh>%d Vertices %d Faces%s%s%s%s</Mesh>" % (
			len(self.vertices),
			len(self.faces),
			"".join(map(str, materials)),
			XML("Normals", self.normal_vertices, self.normal_faces),
			XML("UV-Map", self.uv_vertices, self.uv_faces),
			XML("Vertex-Colors", self.vertex_colors, self.vertex_color_faces)
		)
	
	def get_material_indices(self):
		materials = []
		indices = []
		for material in self.face_materials:
			if not material in materials:
				materials += [material]
			
			indices += [materials.index(material)]
		
		return indices, materials

class Material:
	def __init__(self,
				diffuse=None, hardness=DEFAULT_HARDNESS, specular=None,
				ambient=None, emissive=None, shading_type=DEFAULT_SHADING_TYPE,
				texture=None
			):
		self.diffuse  = diffuse  if diffuse  else list(DEFAULT_DIFFUSE)
		self.specular = specular if specular else list(DEFAULT_SPECULAR)
		self.emissive = emissive if emissive else list(DEFAULT_EMISSIVE)
		self.ambient  = ambient  if ambient  else list(DEFAULT_AMBIENT)
		
		self.hardness = hardness
		self.shading_type = shading_type
		self.texture = texture
		
		if len(self.diffuse) == 3:
			self.diffuse += (1.0,) # Append alpha channel
		
		elif len(self.diffuse) != 4:
			raise TypeError("Material Diffuse color must be RGB or RGBA.")
		
		if len(self.specular) != 3:
			raise TypeError("Material Specular color must be RGB.")
		
		if len(self.emissive) != 3:
			raise TypeError("Material Emissive color must be RGB.")
		
		if len(self.ambient) != 3:
			raise TypeError("Material Ambient color must be RGB.")
	
	def __str__(self):
		return "<Material>%r (%f, %f, %f, %f)</Material>" % (str(self.texture), *self.diffuse)
	
	def __eq__(self, other):
		return (
			self.texture == other.texture
			and self.diffuse      == other.diffuse
			and self.hardness     == other.hardness
			and self.specular     == other.specular
			and self.ambient      == other.ambient
			and self.emissive     == other.emissive
			and self.shading_type == other.shading_type
		)
	
	def __nq__(self, other):
		return not self.__eq__(other)

class AnimationKey:
	TYPE_SIZE = (
		4, # 0: WXYZ Quaternion Rotation
		3, # 1: XYZ Scale
		3, # 2: XYZ Translate
		3  # 3: XYZ Euler Rotation
	)
	
	def __str__(self):
		return "<AnimationKey>%d:%d Keys</AnimationKey>" % (self.key_type, len(self.keys))
	
	def __init__(self, key_type):
		if not key_type in range(4):
			raise ValueError("Invalid Animation Key Type %d" % key_type)
		
		self.key_type = key_type
		self.keys = []
		self.vector_size = __class__.TYPE_SIZE[self.key_type]
	
	def add_key(self, keyframe, vector):
		if len(vector) != self.vector_size:
			raise ValueError("Incorrect Vector Size")
		
		self.keys.append((keyframe, vector))
		
		return self.keys[-1]

class Envelope:
	def __init__(self, bone, vertices=None):
		self.bone = bone # bone is a Frame object which is the bone this envelope refers to.
		self.vertices = vertices if vertices else []
	
	def __str__(self):
		return "<Envelope>Bone %s</Envelope>" % self.bone.name
	
	def add_weight(self, vertex_index, weight_value):
		# (weight_value) is what percent the vertex at index (vertex_index) is influenced by (self.bone)
		self.vertices.append((vertex_index, weight_value))

class XSIParseError(Exception): pass

class Writer:
	def __init__(self, blend2xsi3_xsi, f):
		self.xsi = blend2xsi3_xsi
		self.file = f
		
		if f:
			self.write_xsi()
	
	def get_safe_name(self, name, sub="_"):
		ENABLE_NAME_WARNING = False
		
		if not name:
			name = "unnamed"
			if ENABLE_NAME_WARNING:
				print("XSI WRITER WARNING: Object with no name renamed to %r." % name)
		
		allowed = "QWERTYUIOPASDFGHJKLZXCVBNMqwertyuiopasdfghjklzxcvbnm1234567890_-"
		new_name = "".join((c if c in allowed else sub) for c in name)
		
		if ENABLE_NAME_WARNING and new_name != name:
			print("XSI WRITER WARNING: Object %r renamed to %r." % (new_name, name))
		
		return new_name
	
	def write(self, t=0, data=""):
		self.file.write("\t" * t + data + "\n")
	
	def write_vector_list(self, t, format_string, vectors, type_string=None, type_string2=None, newline_string2=False, total=False):
		if total:
			self.write(t, "%d," % len(vectors))
		
		if type_string:
			self.write(t, "\"%s\"" % type_string + ",")
		
		if type_string2 and newline_string2:
			self.write(t, "\"%s\"" % type_string2 + ",\n")
		elif type_string2:
			self.write(t, "\"%s\"" % type_string2 + ",")
		
		if not vectors: 
			return
		
		for vector in vectors[0:-1]:
			self.write(t, format_string % tuple(vector) + ",")
		else:
			self.write(t, format_string % tuple(vectors[-1]) + ",\n")
	
	def write_animationkeys(self, t, keys):
		self.write(t, "%f," % keys)
		self.write(t, "%f," % keys)
		self.write(t, "%f," % keys)
		if not keys: return
		
		vector_size = len(keys[0][1])
		format_string = "%d; %d; " + ", ".join(["%f"] * vector_size) + ";;%s"
		
		for keyframe, vector in keys[0:-1]:
			self.write(t, format_string % (keyframe, vector_size, *vector, ","))
		self.write(t, format_string % (keys[-1][0], vector_size, *keys[-1][1], ";"))
	
	def write_xsi(self):
		self.write(0, "xsi 0300txt 0032\n") 
		
		blend_filename = bpy.path.basename(bpy.context.blend_data.filepath).replace(" ", "_").removesuffix('.blend')
		
		self.write(0, "SI_FileInfo {")
		self.write(1, "\"%s\"," % blend_filename)
		self.write(1, "\"Blender User\",")
		self.write(1, "\"%s\"," % datetime.now().strftime("%a %b %d %H:%M:%S %Y"))
		self.write(1, "\"Blender Version %d.%d.%d\"," % tuple(bpy.app.version))
		self.write(0, "}\n")
		
		self.write(0, "SI_Scene Blender {") # scene name.
		self.write(1, "\"FRAMES\",")
		self.write(1, "%f," % float(bpy.context.scene.frame_start))
		self.write(1, "%f," % float(bpy.context.scene.frame_end))
		self.write(1, "%f," % (bpy.context.scene.render.fps / bpy.context.scene.render.fps_base))
		self.write(0, "}\n")
		
		self.write(0, "SI_CoordinateSystem coord {")
		self.write(1, "1,")
		self.write(1, "0,")
		self.write(1, "1,")
		self.write(1, "0,")
		self.write(1, "2,")
		self.write(1, "5,")
		self.write(0, "}\n")
		
		self.write(0, "SI_Angle {")
		self.write(1, "0,")
		self.write(0, "}\n")
		
		self.write(0, "SI_Ambience {")
		self.write(1, "0.000000,")
		self.write(1, "0.000000,")
		self.write(1, "0.000000,")
		self.write(0, "}")		
		
		self.write(0, "SI_MaterialLibrary MATLIB-%s {" % blend_filename)
		# FIXME: /vomit. need to get the material data from the scene instead...
		self.write(1, "1,")
		self.write(1, "SI_Material default_material {")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,") 
		self.write(2, "0.000000,")
		self.write(2, "0.000000,") 
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "0.000000,")
		self.write(2, "SI_Texture2D {")
		self.write(3, "\"default_texture\",")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(3, "0.000000,")
		self.write(2, "}\n")		
		self.write(1, "}\n")
		self.write(0, "}")
		
		for root_frame in self.xsi.frames:
			print("Writing object data...")
			
			self.write()
			self.write_si_model(0, root_frame)
		
		skinned_frames = tuple(self.xsi.get_skinned_frames())
		
		if skinned_frames:
			self.write(0, "\nSI_EnvelopeList Blender {")
			self.write(1, "%d," % self.xsi.get_envelope_count())
			
			for frame in skinned_frames:
				for envelope in frame.envelopes:
					self.write_envelope(1, frame, envelope)
			
			self.write(0, "}")
	
	def write_si_model(self, t, frame):
		self.write(t, "SI_Model MDL-%s {" % self.get_safe_name(frame.name))
		
		# Basepose
		if frame.basepose_sca_xyz and frame.basepose_rot_xyz and frame.basepose_pos_xyz:
			self.write_transform(t + 1, frame.basepose_sca_xyz, frame.basepose_rot_xyz, frame.basepose_pos_xyz, "SI_Transform BASEPOSE-%s" % self.get_safe_name(frame.name))

		# FCurve
		#if frame.animation_keys:
			# Scale
			#self.write_animation(t + 1, frame)
			#self.write_animation(t + 1, frame)
			#self.write_animation(t + 1, frame)
			
			# Rotation
			#self.write_animation(t + 1, frame.animation_keys, self.get_safe_name(frame.name), "ROTATION-X")
			#self.write_animation(t + 1, frame.animation_keys, self.get_safe_name(frame.name), "ROTATION-Y")
			#self.write_animation(t + 1, frame.animation_keys, self.get_safe_name(frame.name), "ROTATION-Z")
			
			# Translation
			#self.write_animation(t + 1, frame.animation_keys, self.get_safe_name(frame.name), "TRANSLATION-X")
			#self.write_animation(t + 1, frame.animation_keys, self.get_safe_name(frame.name), "TRANSLATION-Y")
			#self.write_animation(t + 1, frame.animation_keys, self.get_safe_name(frame.name), "TRANSLATION-Z")
		
		# Transform SRT
		if frame.srt_sca_xyz and frame.srt_rot_xyz and frame.srt_pos_xyz:
			self.write_transform(t + 1, frame.srt_sca_xyz, frame.srt_rot_xyz, frame.srt_pos_xyz, "SI_Transform SRT-%s" % self.get_safe_name(frame.name))
		
		# Visibility
		self.write(t + 1, "SI_Visibility {")
		self.write(t + 2, "1,")
		self.write(t + 1, "}\n")
		
		# Null
		if frame.is_bone:
			self.write(t + 1, "SI_Null %s {" % self.get_safe_name(frame.name))
			self.write(t + 1, "}\n")
		
		# Mesh
		if frame.mesh:
			if frame.mesh.face_materials and frame.mesh.faces:
				face_material_indices, materials = frame.mesh.get_material_indices()
				
				for material in materials:
					if material.texture is not None:
						self.write(t + 1, "SI_GlobalMaterial {")
						self.write(t + 2, "\"default_material\"," ) # FIXME: get the material name that's also in the 'SI_MaterialLibrary'...
						self.write(t + 2, "\"NODE\",")
						self.write(t + 1, "}\n")
						
						self.write(t + 1, "XSI_CustomPSet %s {" % self.get_safe_name(frame.name))
						self.write(t + 2, "\"NODE\",")
						self.write(t + 2, "1,")
						
						# use a relative path
						rel_tex_path = str(material.texture)
						rel_tex_path = rel_tex_path.lstrip().split('base\\')[1]
						
						self.write(t + 2, "\"Shader\",\"Text\",\"%s\"," % rel_tex_path) # example: "Shader","Text","models/players/luke/torso.tga",			
						self.write(t + 1, "}\n")
			
			self.write_mesh(t + 1, frame.mesh, frame.mesh.name if frame.mesh.name else frame.name)
		
        # Children
		for sub_frame in frame.frames:
			self.write_si_model(t + 1, sub_frame)
		
		self.write(t, "}\n")
	
	def write_transform(self, t, sca, rot, pos, block_name):
		self.write(t, block_name + " {")
		self.write(t + 1, "%f," % sca[0])
		self.write(t + 1, "%f," % sca[1])
		self.write(t + 1, "%f," % sca[2])
		self.write(t + 1, "%f," % rot[0])
		self.write(t + 1, "%f," % rot[1])
		self.write(t + 1, "%f," % rot[2])		
		self.write(t + 1, "%f," % pos[0])
		self.write(t + 1, "%f," % pos[1])
		self.write(t + 1, "%f," % pos[2])
		self.write(t, "}\n")
	
	def write_fcurve(self, t, keys, name, fcurve_type):
		self.write(t, "SI_FCurve {")
		self.write(t + 1, "\"%s\"," % name)
		self.write(t + 1, "\"%s\"," % fcurve_type)
		self.write(t + 1, "\"LINEAR\",")
		self.write(t + 1, "\"<FCURVE KEY LIST>\",\n")		     
		self.write(t, "}\n")
        
	def write_mesh(self, t, mesh, name):
		self.write(t, "SI_Mesh MSH-%s {" % self.get_safe_name(name))

		if mesh.vertices:
			self.write(t + 1, "SI_Shape SHP-%s-ORG {" % self.get_safe_name(name))
			
			if "bolt_" in self.get_safe_name(name):
				self.write(t + 2, "2,")
			else:
				self.write(t + 2, "3,")
			
			self.write(t + 2, "\"ORDERED\",\n")
			
			self.write_vector_list(t + 2, "%f,%f,%f", mesh.vertices, "POSITION")
			
			if mesh.normal_vertices:
				self.write_vector_list(t + 2, "%f,%f,%f", mesh.normal_vertices, "NORMAL")
				
			if mesh.uv_vertices:
				self.write_vector_list(t + 2, "%f,%f", mesh.uv_vertices, "TEX_COORD_UV")
				
			self.write(t + 1, "}\n")
			
			self.write(t + 1, "SI_TriangleList %s {" % self.get_safe_name(name))
			
			if mesh.faces:
				if mesh.normal_vertices and not mesh.uv_vertices:
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.faces, "NORMAL", "default_material", newline_string2=True, total=True) # FIXME: get the material name that's also in the 'SI_MaterialLibrary'...
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.normal_faces)
				elif mesh.uv_vertices and not mesh.normal_vertices:
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.faces, "TEX_COORD_UV", "default_material", newline_string2=True, total=True) # FIXME: get the material name that's also in the 'SI_MaterialLibrary'...
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.uv_faces)
				elif mesh.normal_vertices and mesh.uv_vertices:
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.faces, "NORMAL|TEX_COORD_UV", "default_material", newline_string2=True, total=True) # FIXME: get the material name that's also in the 'SI_MaterialLibrary'...
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.normal_faces)
					self.write_vector_list(t + 2, "%i,%i,%i", mesh.uv_faces)
			
			self.write(t + 1, "}\n")
		
		self.write(t, "}\n")
	
	def write_material(self, t, material):
		self.write(t, "SI_Material {")
		self.write(t + 1, "%f;%f;%f;%f;;" % tuple(material.diffuse))
		self.write(t + 1, "%f;" % material.hardness)
		self.write(t + 1, "%f;%f;%f;;" % tuple(material.specular))
		self.write(t + 1, "%f;%f;%f;;" % tuple(material.emissive))
		self.write(t + 1, "%d;" % material.shading_type)
		self.write(t + 1, "%f;%f;%f;;" % tuple(material.ambient))
		
		if material.texture:
			self.write(t + 1, "SI_Texture2D {")
			self.write(t + 2, "\"%s\";" % material.texture)
			self.write(t + 1, "}")
		
		self.write(t, "}")
	
	def write_animation(self, t, frame):
		for anim_key in frame.animation_keys:
			# convert key_type to string
			if anim_key.key_type == 1:
				keytype = "SCALING-"
			elif anim_key.key_type == 2:
				keytype = "TRANSLATION-"
			elif anim_key.key_type == 3:
				keytype = "ROTATION-"
			else:
				keytype = "NONE"                
			
			self.write(t + 1, "SI_FCurve {")
			self.write(t + 2, "%s" % keytype)
			self.write_animationkeys(t + 2, anim_key.keys)
			self.write(t + 1, "}")
		
		self.write(t, "}")
	
	def write_envelope(self, t, frame, envelope):
		self.write(t, "SI_Envelope %s {" % self.get_safe_name(frame.name))
		self.write(t + 1, "\"MDL-%s\"," % self.get_safe_name(frame.name))
		self.write(t + 1, "\"MDL-%s\"," % self.get_safe_name(envelope.bone.name))
		self.write_vector_list(t + 1, "%d,%f", envelope.vertices)
		self.write(t, "}")
