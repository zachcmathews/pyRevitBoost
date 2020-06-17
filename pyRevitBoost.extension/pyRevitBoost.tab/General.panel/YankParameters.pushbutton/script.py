# pylint: disable=import-error
import os
import sys
import re
from functools import partial

from Autodesk.Revit.DB import BuiltInParameter, FamilyInstance

import rpw
from pyrevit import script, forms
from boostutils import get_parameter, load_as_python

__doc__ = '''\
Yank parameters from nearest in linked models.

Shift+Click = Edit configuration file.
'''
__title__ = 'Yank\nParameters'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def get_link_instance(title):
    return rpw.db.Collector(
        of_category='OST_RvtLinks',
        of_class='RevitLinkInstance',
        where=partial(doc_title_filter, title=title)
    ).get_first(wrapped=False)


def doc_title_filter(link, title):
    if title in link.GetLinkDocument().Title:
        return True


def family_filter(el, family):
    return (
        get_parameter(
            el,
            builtin='ELEM_FAMILY_PARAM'
        ).AsValueString() in families
    )


def phase_filter(el, phase, phase_map, current_phase):
    if phase_map:
        if phase == '<current>':
            return get_parameter(
                el,
                builtin='PHASE_CREATED'
            ).AsElementId() == phase_map[current_phase]
        else:
            return get_parameter(
                el,
                builtin='PHASE_CREATED'
            ).AsValueString() == phase

    else:
        if phase == '<current>':
            return get_parameter(
                el,
                builtin='PHASE_CREATED'
            ).AsElementId() == current_phase
        else:
            return get_parameter(
                el,
                builtin='PHASE_CREATED'
            ).AsValueString() == phase


def type_filter(el, type):
    return (
        get_parameter(el, builtin='ELEM_TYPE_PARAM').AsValueString() == type
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


def get_filters(mapping, current_phase, link_type):
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
            phase=mapping['phase'],
            phase_map=link_type.GetPhaseMap() if link_type else None,
            current_phase=current_phase
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


def pair(el, others, others_transform):
    closest, min_distance = None, 0
    for other in others:
        if others_transform:
            distance = others_transform.OfPoint(other.Location.Point)\
                                       .DistanceTo(el.Location.Point)
        else:
            distance = other.Location.Point.DistanceTo(el.Location.Point)

        if closest is None or distance < min_distance:
            closest, min_distance = other, distance

    return {
        'from': closest,
        'to': el
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


if __name__ == '__main__':
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    view = uidoc.ActiveView
    current_phase = \
        view.get_Parameter(BuiltInParameter.VIEW_PHASE).AsElementId()
    selection = rpw.ui.Selection()

    script_config = script.get_config(
        section='pyRevitBoost.General.YankParameters'
    )
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

    cnt = 0
    total = len(selection)
    failed = set()
    not_yanked = set(e.unwrap().Id for e in selection.get_elements())
    with forms.ProgressBar(title='{value} of {max_value}') as pb:
        with rpw.db.Transaction('Yank parameters'):
            for mapping in mappings:
                link_instance = get_link_instance(mapping['from'].get('model'))
                if link_instance:
                    link_type = doc.GetElement(link_instance.GetTypeId())
                    from_doc = link_instance.GetLinkDocument()
                else:
                    link_type = None
                    from_doc = doc

                # Gather 'from' elements
                filters = get_filters(
                    mapping['from'],
                    current_phase=current_phase,
                    link_type=link_type
                )
                from_elements = rpw.db.Collector(
                    doc=from_doc,
                    of_category=mapping['from']['category'],
                    of_class=FamilyInstance,
                    where=lambda e: all(f(e.unwrap()) for f in filters) \
                                    if filters else True
                ).get_elements(wrapped=False)

                # Gather 'to' elements
                filters = get_filters(
                    mapping['to'],
                    current_phase=current_phase,
                    link_type=link_type
                )
                to_elements = rpw.db.Collector(
                    elements=selection.get_elements(),
                    of_category=mapping['to']['category'],
                    of_class=FamilyInstance,
                    where=lambda e: all(f(e.unwrap()) for f in filters) \
                                    if filters else True
                ).get_elements(wrapped=False)

                # Remove from not_yanked
                for e in to_elements:
                    not_yanked.discard(e.Id)

                if not from_elements or not to_elements:
                    failed.update(to_elements)
                    cnt += len(to_elements)
                    pb.update_progress(
                        new_value=cnt,
                        max_value=total
                    )
                    continue

                xfm = link_instance.GetTotalTransform() if link_instance else None
                pairs = (
                    pair(
                        el=e,
                        others=from_elements,
                        others_transform=xfm
                    ) for e in to_elements
                )
                for _pair in pairs:
                    try:
                        yank(_pair, mapping)
                    except:
                        failed.update(to_elements)
                        cnt += len(to_elements)
                        pb.update_progress(
                            new_value=cnt,
                            max_value=total
                        )
                        continue

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
