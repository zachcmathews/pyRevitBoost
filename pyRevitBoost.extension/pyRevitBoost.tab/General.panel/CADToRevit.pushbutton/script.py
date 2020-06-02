# pylint: disable=import-error
import sys
import time

from Autodesk.Revit.Exceptions import ArgumentException

import rpw
from pyrevit import forms, script
from boostutils import load_as_python

from parse import parse_config
from place import map_block_to_family_instance
from gather import (get_blocks, get_cad_imports,
                    get_family_types, get_reference_planes,
                    group_blocks_by_name)

__doc__ = '''\
Map imported CAD blocks to their equivalent Revit family type. \
Requires configuration specified in config.yaml.

Shift+Click = Draw circle at block locations. Useful for setting \
offsets in config.yaml.
'''
__title__ = 'CAD -> Revit'
__author__ = 'Zachary Mathews'
__cleanengine__ = True

start_time = time.time()

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView
level = view.GenLevel

config = load_as_python(script.get_bundle_file('config.yaml'))

family_types = get_family_types()
reference_planes = get_reference_planes()
cad_imports = get_cad_imports()

# Select DWG import if more than one
if not cad_imports:
    forms.alert(
        title='No CAD import (or none selected)',
        msg='You must have a CAD import to use this command.'
    )
    sys.exit()

if len(cad_imports) > 1:
    cad_import = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='Name'
    )
else:
    forms.alert(
        title='Convert CAD to Revit',
        msg='Are you sure you wish to map CAD blocks to Revit families?',
        ok=False,
        yes=True,
        no=True,
        exitscript=True
    )
    [cad_import] = cad_imports

if not cad_import:
    sys.exit()

# Gather import geometry
import_transform = cad_import.GetTotalTransform()
blocks = get_blocks(cad_import)
blocks_grouped_by_name = group_blocks_by_name(blocks)

cnt = 0
total = len(blocks)
no_mapping = {}
failed = []
with forms.ProgressBar(title='{value} of {max_value}', step=20) as pb:
    with rpw.db.Transaction('CAD -> Revit') as t:
        for block_name, blocks in blocks_grouped_by_name.items():
            if not config:
                no_mapping[block_name] = blocks
                cnt += len(blocks)
                pb.update_progress(cnt, total)
                continue

            mapping = parse_config(block_name, config, doc)
            if not mapping:
                no_mapping[block_name] = blocks
                cnt += len(blocks)
                pb.update_progress(cnt, total)
                continue

            for block in blocks:
                try:
                    map_block_to_family_instance(
                        family_type=mapping['family_type'],
                        host=mapping['host'],
                        origin_offset=mapping['origin_offset'],
                        orientation_offset=mapping['orientation_offset'],
                        parameters=mapping['parameters'],
                        block=block,
                        transform=import_transform,
                        doc=doc,
                        view=view,
                        level=level,
                    )
                except (TypeError, ArgumentException):
                    failed.append(block)
                finally:
                    cnt += 1
                    pb.update_progress(cnt, total)


no_mapping_count = sum(len(blocks) for blocks in no_mapping.values())
config_warning = (
    'No viable mapping found for {} blocks:\n'.format(no_mapping_count) +
    '\n'.join([
       '{} : {} blocks'.format(name, len(blocks))
       for (name, blocks) in sorted(no_mapping.items())
    ])
)
results = (
    'Processed {0} elements in {1:4} seconds.\n'
    .format(total, time.time()-start_time) +
    'Successfully placed {} elements.\n'
    .format(total-no_mapping_count-len(failed)) +
    'Failed to place {} elements.'.format(len(failed))
)
forms.alert(
    title='Results',
    msg='{}\n\n{}'.format(config_warning, results)
)
