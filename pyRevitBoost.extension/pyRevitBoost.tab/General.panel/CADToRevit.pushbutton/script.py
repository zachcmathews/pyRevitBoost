# pylint: disable=import-error
import os
import sys
import time

from Autodesk.Revit.Exceptions import ArgumentException

import rpw
from pyrevit import forms, script
from boostutils import get_parameter, load_as_python, load_tsv

from parse import parse_config
from place import map_block_to_family_instance
from gather import (get_blocks, get_cad_imports,
                    get_family_types, get_reference_planes,
                    group_blocks_by_name)

__doc__ = u'''\
Map imported CAD blocks to their equivalent Revit family type. \
Requires configuration specified in config.yaml.

Shift+Click =
    - Draw circle at block locations. Useful for setting \
offsets in config.yaml.
    - Edit configuration file.
'''
__title__ = u'CAD\U00002b62Revit'
__author__ = 'Zachary Mathews'
__cleanengine__ = True

start_time = time.time()

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView
level = view.GenLevel

script_config = script.get_config(section='pyRevitBoost.General.CADToRevit')
reuse_config = False
if hasattr(script_config, 'config_file'):
    config_file=script_config.config_file
    if os.path.isfile(script_config.config_file):
        reuse_config = forms.alert(
            title='CAD -> Revit',
            msg='Reuse previous configuration?',
            sub_msg=config_file,
            ok=False,
            yes=True,
            no=True,
            warn_icon=False
        )
if not reuse_config:
    with forms.WarningBar(title='Please select a configuration file'):
        config_file = forms.pick_file(
            files_filter='YAML Configuration File (*.yaml)|*.yaml|'
                         'Tab-separated Values File (*.tsv)|*.tsv',
            restore_dir=True
        )
if not config_file:
    sys.exit()

if config_file.endswith('.yaml'):
    config = load_as_python(config_file)
elif config_file.endswith('.tsv'):
    config = load_tsv(
        config_file,
        use_headers=['block', 'category', 'family', 'type', 'host'],
        skip_first=True
    )

if config is not None:
    script_config.config_file = config_file
    script.save_config()

family_types = get_family_types()
reference_planes = get_reference_planes()
cad_imports = get_cad_imports()
if not cad_imports:
    forms.alert(
        title='No CAD import',
        msg='You must have a CAD import to use this command.'
    )
    sys.exit()

# Select DWG import if more than one
if len(cad_imports) > 1:
    cad_import = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='name'
    )
else:
    cad_import = cad_imports[0]

if not cad_import:
    sys.exit()
else:
    cad_import = cad_import._import   # we no longer care about name

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
    msg='{}\n\n{}'.format(config_warning, results),
    warn_icon=False
)
