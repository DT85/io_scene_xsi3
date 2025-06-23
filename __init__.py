bl_info = {
	"name": "Softimage XSI 3.0 format",
	"author": "FruteSoftware@gmail.com, Tempust85",
	"version": (1, 0, 0),
	"blender": (4, 2, 0),
	"location": "File > Import-Export",
	"description": "Softimage XSI 3.0 Exporter",
	"category": "Import-Export"
}

import bpy

from bpy.props import (
	StringProperty,
	BoolProperty,
	FloatProperty,
	EnumProperty
)

from bpy_extras.io_utils import (
	ExportHelper,
	orientation_helper,
	axis_conversion
)

if "bpy" in locals():
	import importlib
	if "blend2xsi" in locals(): importlib.reload(blend2xsi)
	if "xsi_blender_exporter" in locals(): importlib.reload(xsi_blender_exporter)


class ExportXSI(bpy.types.Operator, ExportHelper):
	"""Export Softimage XSI 3.0 file"""
	bl_idname = "export_scene.io_scene_blend2xsi"
	bl_label = "Export XSI"
	bl_options = {"UNDO", "PRESET"}
	
	directory: StringProperty(subtype="DIR_PATH")
	filename_ext = ".xsi"
	filter_glob: StringProperty(default="*.xsi", options={'HIDDEN'})
	
	export_mode: EnumProperty(
		items=(
			("ACTIVE_COLLECTION", "Active Collection", "Export objects in active collection", "OUTLINER_COLLECTION", 1),
			("SELECTED_OBJECTS", "Only Selected Objects", "Export selected objects, including child objects", "OUTLINER", 2)
		),
		
		name="Export Mode",
		description="Which objects are to be exported",
		default="ACTIVE_COLLECTION"
	)

	export_mesh: BoolProperty(
		name="Mesh",
		description="Export mesh data",
		default=True
	)

	export_mesh_uvmap: BoolProperty(
		name="UV Map",
		description="Export mesh UV map coordinates",
		default=True
	)

	export_mesh_materials: BoolProperty(
		name="Materials",
		description="Export mesh materials",
		default=True
	)

	export_mesh_vertcolor: BoolProperty(
		name="Vertex Colors",
		description="Export mesh vertex colors",
		default=True
	)

	export_envelopes: BoolProperty(
		name="Bone Envelopes",
		description="Export skin envelopes for bones",
		default=True
	)

	export_animations: BoolProperty(
		name="Animations",
		description="Export rotation & translation animations",
		default=True
	)
	
	export_euler: BoolProperty(
		name="Euler Animation Keys",
		description="Export animation keys as euler instead of quaternion",
		default=True
	)
	
	zero_root_transforms: BoolProperty(
		name="Reset Root Transforms",
		description="Root-level objects have default transform matrices",
		default=True
	)

	generate_empty_mesh: BoolProperty(
		name="Generate Empty Meshes",
		description="Create a pointer-like mesh for empty objects to visualize their direction (e.g. for hardpoints)",
		default=False
	)

	generate_bone_mesh: BoolProperty(
		name="Generate Meshes For Bones",
		description="Create meshes for bones to visualize bones for debugging purposes",
		default=False
	)
	
	def draw(self, context):
		layout = self.layout
		
		export_layout = layout.box()
		export_layout.prop(self, "export_mode", expand=True)
		if self.export_mode == "ACTIVE_COLLECTION":
			collection = bpy.context.view_layer.active_layer_collection.collection
			export_layout.label(text="%s (%d objects)" % (collection.name, len(collection.objects)))
		layout.separator()
		
		mesh_layout = layout.box()
		mesh_layout.prop(self, "export_mesh", icon="MESH_DATA")
		
		sub = mesh_layout.column()
		sub.prop(self, "export_mesh_uvmap", icon="GROUP_UVS")
		sub.enabled = self.export_mesh
		
		sub = mesh_layout.column()
		sub.prop(self, "export_mesh_materials", icon="MATERIAL_DATA")
		sub.enabled = self.export_mesh

		sub = mesh_layout.column()
		sub.prop(self, "export_mesh_vertcolor", icon="GROUP_VCOL")
		sub.enabled = self.export_mesh
		
		sub = mesh_layout.column()
		sub.prop(self, "export_envelopes", icon="GROUP_VERTEX")
		sub.enabled = self.export_mesh
		mesh_layout.separator()
		
		sub = mesh_layout.column()
		sub.prop(self, "generate_empty_mesh", icon="EMPTY_DATA")
		sub.enabled = self.export_mesh
		layout.separator()
        
		anim_layout = layout.box()
		anim_layout.prop(self, "export_animations", icon="ARMATURE_DATA")
		anim_layout.separator()
		
		anim_sub = anim_layout.column()
		anim_sub.prop(self, "export_euler", icon="KEYFRAME")
		anim_sub.enabled = self.export_animations
		anim_layout.separator()
		
		anim_sub = anim_layout.column()
		anim_sub.prop(self, "generate_bone_mesh", icon="GROUP_BONE")
		anim_sub.enabled = self.export_animations
		layout.separator()
		
		zero_transform = layout.column()
		zero_transform.prop(self, "zero_root_transforms", icon="ORIENTATION_GLOBAL")
	
	def execute(self, context):
		from . import xsi_blender_exporter
		keywords = self.as_keywords(ignore=("filter_glob", "directory"))
		return xsi_blender_exporter.save(self, context, **keywords)

def menu_func_export(self, context):
	self.layout.operator(ExportXSI.bl_idname, text="Softimage XSI 3.0 (.xsi)")

def register():
	bpy.utils.register_class(ExportXSI)

	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

	bpy.utils.unregister_class(ExportXSI)

if __name__ == "__main__":
	register()
