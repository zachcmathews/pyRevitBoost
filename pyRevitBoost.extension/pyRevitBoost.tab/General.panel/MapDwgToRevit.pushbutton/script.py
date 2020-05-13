# pylint: disable=import-error
from Autodesk.Revit.DB import CADLinkType, Element, FilteredElementCollector, ImportInstance, GraphicsStyle, ElementType

import rpw
from pyrevit import forms, script
from boostutils import load_as_python

__doc__ = '''Map imported AutoCAD blocks to their equivalent Revit family type.
Requires configuration file config.yaml'''
__title__ = 'Convert\nDWG Blocks'
__author__ = 'Zachary Mathews'

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc

# Get configuration file
config = load_as_python(script.get_bundle_file('config.yaml'))

# Get DWG imports
cad_imports = FilteredElementCollector(doc) \
    .OfClass(CADLinkType) \
    .ToElements()

# Select DWG import if more than one
if len(cad_imports) > 1:
    dwg = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='Name'
    )
else:
    [dwg] = cad_imports

# Gather AutoCAD blocks
blocks = [doc.GetElement(id) for id in dwg.GetDependentElements(None)]
print(set(b.Name for b in blocks if b.hasAttr('Name') and b.Name == 'NGHS-tmp.dwg.2X4L_888'))

cnt = 0
total = len(blocks)
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    cnt += 1
    pb.update_progress(cnt, total)
