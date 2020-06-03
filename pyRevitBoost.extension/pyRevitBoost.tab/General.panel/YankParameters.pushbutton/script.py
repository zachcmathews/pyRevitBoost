# pylint: disable=import-error
import os
import sys
import re
from functools import partial, reduce

from Autodesk.Revit.DB import (BuiltInParameter, FamilyInstance,
                               FilteredElementCollector)

import rpw
from pyrevit import script, forms
from boostutils import find_closest, get_parameter, load_as_python

__doc__ = '''\
Yank parameters from nearest in linked models.

Shift+Click = Edit configuration file.
'''
__title__ = 'Yank\nParameters'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc
view = uidoc.ActiveView
current_phase = view.get_Parameter(BuiltInParameter.VIEW_PHASE).AsElementId()
selection = rpw.ui.Selection()

script_config = script.get_config(section='pyRevitBoost.General.YankParameters')
reuse_config = False
if hasattr(script_config, 'config_file'):
    config_file=script_config.config_file
    if os.path.isfile(script_config.config_file):
        reuse_config = forms.alert(
            title='YankParameters',
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
            file_ext='yaml',
            restore_dir=True
        )
if not config_file:
    sys.exit()

mappings = load_as_python(config_file)
if mappings:
    script_config.config_file = config_file
    script.save_config()


def family_filter(el, family):
    return (
        get_parameter(
            el,
            builtin='ELEM_FAMILY_PARAM'
        ).AsValueString() in families
    )


def phase_filter(el, phase):
    return get_parameter(el, builtin='PHASE_CREATED').AsValueString() == phase


def type_filter(el, type):
    return (
        get_parameter(
            el,
            builtin='ELEM_TYPE_PARAM'
        ).AsValueString() == type
    )


def parameter_filter(el, parameter):
    pattern = r'^(?P<parameter>.+?)\s*(?P<comparison_operator>=|>|<|>=|<=)\s*(?P<value>.+)$'
    match = re.search(pattern, parameter)
    if not match:
        return None

    filter = {
        'name': match.group('parameter'),
        'comparison_operator': match.group('comparison_operator'),
        'value': match.group('value')
    }
    parameter = get_parameter(el, name=filter['name'])

    if filter['comparison_operator'] == '=':
        value = parameter.AsString()
        return value == filter['value']

    elif filter['comparison_operator'] == '>':
        value = parameter.AsDouble()
        return value > float(filter['value'])

    elif filter['comparison_operator'] == '<':
        value = parameter.AsDouble()
        return value < float(filter['value'])

    elif filter['comparison_operator'] == '>=':
        value = parameter.AsDouble()
        return value >= float(filter['value'])

    elif filter['comparison_operator'] == '<=':
        value = parameter.AsDouble()
        return value <= float(filter['value'])


def get_filters(mapping):
    global family_filter, type_filter, phase_filter, parameter_filter
    filters = []

    if mapping.get('family'):
        family_filter = partial(
            family_filter,
            family=mapping['family']
        )
        filters.append(family_filter)

    if mapping.get('type'):
        type_filter = partial(
            type_filter,
            type=mapping['type']
        )
        filters.append(type_filter)

    if mapping.get('phase'):
        phase_filter = partial(
            phase_filter,
            phase=mapping['phase']
        )
        filters.append(phase_filter)

    if mapping.get('exclude'):
        for parameter in mapping['exclude']:
            parameter_filter = partial(
                parameter_filter,
                parameter=parameter
            )
            filters.append(lambda e: not parameter_filter(e))

    return filters


def pair(to, others):
    closest = find_closest(
        to=to,
        elements=others
    )
    return {
        'from': closest,
        'to': to
    }


def yank(pair, mapping):
    value = ''
    for name in mapping['from']['parameters']:
        pattern = r'^separator\((?P<separator>.+)\)$'
        match = re.search(pattern, name)
        if match:
            value += match.group('separator')
        else:
            parameter = get_parameter(pair['from'], name=name)
            _pval = parameter.AsString()
            value += _pval if _pval else ''

    for name in mapping['to']['parameters']:
        parameter = get_parameter(pair['to'], name=name)
        parameter.Set(value)


cnt = 0
total = len(selection)
failed = []
not_yanked = [e.unwrap().Id for e in selection.get_elements()]
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.Transaction('Yank parameters'):
        for mapping in mappings:
            # Gather 'from' elements
            filters = get_filters(mapping['from'])
            from_elements = rpw.db.Collector(
                of_category=mapping['from']['category'],
                of_class=FamilyInstance,
                view=view,
                where=lambda e: all(f(e.unwrap()) for f in filters) \
                                if filters else True
            ).get_elements(wrapped=False)

            # Gather 'to' elements
            filters = get_filters(mapping['to'])
            to_elements = rpw.db.Collector(
                elements=selection.get_elements(),
                of_category=mapping['to']['category'],
                of_class=FamilyInstance,
                where=lambda e: all(f(e.unwrap()) for f in filters) \
                                if filters else True
            ).get_elements(wrapped=False)

            # Remove from not_yanked
            [not_yanked.remove(e.Id) for e in to_elements if e.Id in not_yanked]

            if not from_elements or not to_elements:
                failed.extend(to_elements)
                cnt += len(to_elements)
                pb.update_progress(
                    new_value=cnt,
                    max_value=total
                )
                continue

            # Pair 'from' and 'to' elements based on proximity
            pairs = [pair(e, from_elements) for e in to_elements]
            [yank(pair, mapping) for pair in pairs]

            cnt += len(to_elements)
            pb.update_progress(
                new_value=cnt,
                max_value=total
            )

if failed or not_yanked:
    failed_msg = (
        'Failed to yank parameters from nearest for {} selected element{}.'
    ).format(len(failed), 's' if len(failed) > 1 else '')

    not_yanked_msg = (
        'No viable yank found for {} selected element{}.'
    ).format(len(not_yanked), 's' if len(failed) > 1 else '')

    total_msg = (
        'Total selected: {}'.format(len(failed) + len(not_yanked))
    )

    msg = (failed_msg if failed else '') + '\n\n' + \
          (not_yanked_msg if not_yanked else '') + '\n\n' + \
          (total_msg if failed or not_yanked else '')
    forms.alert(
        title='Error',
        msg=msg
    )
    selection.clear()
    selection.add(failed)
    selection.add(not_yanked)
