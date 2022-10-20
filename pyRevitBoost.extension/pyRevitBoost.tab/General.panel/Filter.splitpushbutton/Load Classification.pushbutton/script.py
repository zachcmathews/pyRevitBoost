# pylint: disable=import-error
import sys

from Autodesk.Revit.DB import BuiltInParameter, Domain, ElementId
from Autodesk.Revit.DB.Electrical import ElectricalSystemType

from pyrevit import forms
import rpw

__doc__ = '''\
Filter elements by connector load classification.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)

    elements_by_load_classification = {}
    for e in elements:
        if not hasattr(e, 'MEPModel'):
            continue

        mep_model = e.MEPModel
        if not mep_model:
            continue

        cm = mep_model.ConnectorManager
        if not cm:
            continue

        connectors = cm.Connectors
        if not connectors:
            continue

        load_classifications = set()
        for c in connectors:
            if c.Domain != Domain.DomainElectrical:
                continue

            if c.ElectricalSystemType != ElectricalSystemType.PowerCircuit:
                continue

            c_info = c.GetMEPConnectorInfo()
            if not c_info:
                continue

            lc_id = \
                c_info.GetConnectorParameterValue(
                    ElementId(
                        getattr(
                            BuiltInParameter, 'RBS_ELEC_LOAD_CLASSIFICATION'))
                ).Value
            if not lc_id:
                continue

            lc = doc.GetElement(lc_id)
            if not lc:
                continue

            load_classifications.add(lc.Name)

        for c in load_classifications:
            if c in elements_by_load_classification:
                elements_by_load_classification[c].append(e)
            else:
                elements_by_load_classification[c] = [e]

    if not elements_by_load_classification:
        sys.exit()

    selected = forms.SelectFromList.show(
        context=elements_by_load_classification.keys(),
        title='Select load classifications',
        multiselect=True)
    if not selected:
        sys.exit()

    selection.clear()
    for lc in selected:
        selection.add(elements_by_load_classification[lc])


if __name__ == '__main__':
    main()
