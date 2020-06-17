# pylint: disable=import-error
# NOTE: Uses hacky work-around to create alignment with hatch line
# https://forums.autodesk.com/t5/revit-api-forum/use-of-align-function-programatically-to-change-the-alignment-of/td-p/6008184
import sys
from System.Collections.Generic import List
from collections import OrderedDict

from Autodesk.Revit.DB import ElementId

from pyrevit import forms
import rpw

from gather import (find_hosted_fixtures, get_ceilings,
                    get_ceiling_representation, get_fixture_edges,
                    get_fixtures_of_category, get_links)
from align import (align_ceiling_representation_with_gridlines,
                   align_grid_with_edges)

__doc__ = '''Align ceilings with fixtures.'''
__title__ = 'Align\nCeilings'
__author__ = 'Zachary Mathews'
__context__ = 'Ceilings'
__cleanengine__ = True

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc
view = uidoc.ActiveView

selected = uidoc.Selection.GetElementIds()
if not selected:
    forms.alert(
        msg='You must first select ceilings.',
        title='Error'
    )
    sys.exit()

ceilings = get_ceilings(selected=selected, doc=doc)
if not ceilings:
    forms.alert(
        msg='You must first select ceilings.',
        title='Error'
    )
    sys.exit()

class DocumentOption(forms.TemplateListItem):
    @property
    def name(self):
        return self.item.Title

links = get_links(doc)
docs = [DocumentOption(doc)]
for link in links:
    link_doc = link.GetLinkDocument()
    if link_doc:
        docs.append(DocumentOption(link_doc))

fixtures_doc = forms.SelectFromList.show(
    context=docs,
    title='Select model',
    width=400,
    height=400,
    multiselect=False
)

categories = fixtures_doc.Settings.Categories
selected_category = forms.SelectFromList.show(
    context=sorted([category.Name for category in categories]),
    title='Select category',
    width=400,
    height=600,
    multiselect=False
)
[category] = [c for c in categories if c.Name == selected_category]

fixtures = get_fixtures_of_category(category=category, doc=fixtures_doc)
if not fixtures:
    forms.alert(
        msg='The selected model does not contain fixtures of that category.',
        title='Error'
    )
    sys.exit()

cnt = 0
max = len(ceilings)
failed = []
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.TransactionGroup('Align ceilings with light fixtures'):

        with rpw.db.Transaction('Create representation of ceiling grids'):
            ceiling_grids, failed = get_ceiling_representation(
                ceilings=ceilings,
                view=view,
                doc=doc
            )

            failed.extend(failed)
            cnt += len(failed)
            pb.update_progress(cnt, max)

        with rpw.db.Transaction('Align representation with gridlines'):
            for ceiling, grid in ceiling_grids:
                align_ceiling_representation_with_gridlines(
                    ceiling=ceiling,
                    grid=grid,
                    view=view,
                    doc=doc
                )

        with rpw.db.Transaction('Align gridlines with edges'):
            for ceiling, grid in ceiling_grids:
                # Get fixtures under the current ceiling
                hosted_fixtures = find_hosted_fixtures(
                    ceiling=ceiling,
                    fixtures=fixtures
                )

                # Get fixture edges
                edges_in_ceiling = []
                for fixture in hosted_fixtures:
                    edges_in_ceiling.extend(get_fixture_edges(fixture, view))

                # Align grid with fixture edges
                succeeded, _failed = align_grid_with_edges(
                    grid=grid,
                    edges=edges_in_ceiling,
                    doc=doc
                )
                if _failed:
                    failed.append(ceiling)

                # Cleanup
                reference_planes = [l['reference_plane'].Id for l in grid]
                doc.Delete(List[ElementId](reference_planes))

                # Update progress
                cnt += 1
                pb.update_progress(cnt, max)


if failed:
    uidoc.Selection.SetElementIds(List[ElementId]([e.Id for e in failed]))
    forms.alert(
        title='Error',
        msg='Align Ceilings failed for {} ceiling{}.\n{} left selected.'
            .format(
                len(failed),
                's' if len(failed) > 1 else '',
                'They were' if len(failed) > 1 else 'It was'
            )
    )
