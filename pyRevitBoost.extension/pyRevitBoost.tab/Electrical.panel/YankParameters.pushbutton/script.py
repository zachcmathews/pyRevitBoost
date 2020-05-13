# pylint: disable=import-error
import sys
import re

from Autodesk.Revit.DB import (BuiltInParameter, FamilyInstance,
                               FilteredElementCollector)

import rpw
from pyrevit import script, forms
from boostutils import find_closest, get_parameter, load_as_python

__doc__ = '''Yank parameters from nearest in linked models.'''
__title__ = 'Yank\nParameters'
__author__ = 'Zachary Mathews'

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc
view = uidoc.ActiveView
phase = view.get_Parameter(BuiltInParameter.VIEW_PHASE).AsElementId()

mappings = load_as_python(script.get_bundle_file('config.yaml'))

selected = uidoc.Selection.GetElementIds()
if not selected:
    sys.exit()

cnt = 0
total = len(selected)
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.Transaction('Yank parameters'):
        for mapping in mappings:
            # Gather 'from' and 'to' elements
            from_elements = FilteredElementCollector(doc) \
                .OfCategoryId(
                    doc.Settings.Categories[mapping['from']['category']].Id
                ) \
                .OfClass(FamilyInstance) \
                .ToElements()

            to_elements = FilteredElementCollector(doc, selected) \
                .OfCategoryId(
                    doc.Settings.Categories[mapping['to']['category']].Id
                ) \
                .OfClass(FamilyInstance) \
                .ToElements()

            # Pair 'from' and 'to' elements based on 'rule'
            rule = mapping['rule']
            pairs = []
            if rule == 'closest':
                for to_element in to_elements:
                    pairs.append({
                        'from': find_closest(
                            to=to_element,
                            elements=from_elements
                        ),
                        'to': to_element
                    })

            # Yank parameter from 'from' to 'to' in each pair
            for pair in pairs:
                from_parameters = mapping['from']['parameters']
                to_parameters = mapping['to']['parameters']

                # Concatenate parameter values in from_parameters
                value = ''
                for parameter_name in from_parameters:
                    pattern = r'^separator\((?P<separator>.+)\)$'
                    match = re.search(pattern, parameter_name)
                    if match:
                        value += match.group('separator')
                    else:
                        parameter = \
                            get_parameter(pair['from'], parameter_name)
                        value += parameter.AsString() or ''

                for parameter in to_parameters:
                    parameter = get_parameter(pair['to'], parameter)
                    parameter.Set(value)

                cnt += 1
                pb.update_progress(
                    new_value=cnt,
                    max_value=total
                )
