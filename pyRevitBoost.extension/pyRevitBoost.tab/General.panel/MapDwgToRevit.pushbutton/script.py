# pylint: disable=import-error
import contextlib

from Autodesk.Revit.Exceptions import ArgumentException

import rpw
from pyrevit import forms, script
from boostutils import load_as_python

from parse import parse_config
from place import map_block_to_family_instance
from gather import (get_blocks, get_cad_imports,
                    get_family_types, get_reference_planes,
                    group_blocks_by_name)

__doc__ = 'Map imported CAD blocks to their equivalent Revit family \
type. Requires configuration file config.yaml'
__title__ = 'Convert\nDWG Blocks'
__author__ = 'Zachary Mathews'

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView
level = view.GenLevel

config = load_as_python(script.get_bundle_file('config.yaml'))

family_types = get_family_types()
reference_planes = get_reference_planes()
cad_imports = get_cad_imports()

# Select DWG import if more than one
if len(cad_imports) > 1:
    cad_import = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='Name'
    )
else:
    [cad_import] = cad_imports
import_transform = cad_import.GetTotalTransform()

blocks = get_blocks(cad_import)
blocks_grouped_by_name = group_blocks_by_name(blocks)

cnt = 0
total = len(blocks)
no_mapping = {}
failed = []
with contextlib.nested(
    forms.ProgressBar(title='{value} of {max_value}', step=20),
    rpw.db.Transaction('CAD -> Revit')
) as (pb, t):
    for block_name, blocks in blocks_grouped_by_name.items():
        family_type, host = parse_config(block_name, config)
        if not family_type or not host:
            no_mapping[block_name] = blocks
            cnt += len(blocks)
            pb.update_progress(cnt, total)
            continue

        for block in blocks:
            try:
                map_block_to_family_instance(
                    family_type=family_type,
                    host=host,
                    block=block,
                    transform=import_transform,
                    doc=doc,
                    view=view,
                    level=level,
                )
            except ArgumentException:
                failed.append(block)
            finally:
                cnt += 1
                pb.update_progress(cnt, total)


no_mapping_count = sum(len(blocks) for blocks in no_mapping.values())
config_warning = (
    'No mapping found for {} blocks:\n'.format(no_mapping_count) +
    '\n'.join([
       '{} : {} blocks'.format(name, len(blocks))
       for (name, blocks) in sorted(no_mapping.items())
    ])
)
results = (
    'Processed {} elements.\n'.format(total) +
    'Successfully placed {} elements.\n'
    .format(total-no_mapping_count-len(failed)) +
    'Failed to place {} elements.'.format(len(failed))
)
forms.alert(
    title='Results',
    msg='{}\n\n{}'.format(config_warning, results)
)
