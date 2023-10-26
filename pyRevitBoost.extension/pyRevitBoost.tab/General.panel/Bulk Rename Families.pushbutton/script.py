# pylint: disable=import-error
import sys
import rpw
from pyrevit import forms

__doc__ = '''\
Bulk rename families in this project.
'''
__title__ = 'Bulk Rename Families'
__author__ = 'Zachary Mathews'


if __name__ == '__main__':
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    families = rpw.db.Collector(
        of_class='Family'
    ).get_elements(wrapped=False)

    selected_families = forms.SelectFromList.show(
        sorted(families, key=lambda f: f.Name),
        multiselect=True,
        name_attr='Name',
        button_name='Rename Families'
    )

    if not selected_families:
        sys.exit()

    selected_option = forms.CommandSwitchWindow.show(
        ['Prepend', 'Append']
    )

    if not selected_option:
        sys.exit()

    text = forms.ask_for_string(
        default='',
        prompt='{} text: '.format(selected_option)
    )

    if not text:
        sys.exit()

    with rpw.db.Transaction('Bulk Rename Families', doc=doc):
        for family in selected_families:
            if selected_option == 'Prepend':
                family.Name = text + family.Name

            elif selected_option == 'Append':
                family.Name = family.Name + text
