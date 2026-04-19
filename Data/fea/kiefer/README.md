### FEA DataSet - Steve Kiefer


This dataset was obtained from Steve Kiefer's
[shkiefer/dash_vtk_unstructured](https://github.com/shkiefer/dash_vtk_unstructured)
repository, which is referenced by his Medium article [3D mesh models in the browser using python & dash_vtk](https://towardsdatascience.com/3d-mesh-models-in-the-browser-using-python-dash-vtk-e15cbf36a132).


Data was pulled and post-processed with:

```
git clone https://github.com/shkiefer/dash_vtk_unstructured
cd dash_vtk_unstructured
```

Run app, insert `grid.write('grid.vtu')` at [dash_vtk_unstructured.py Line 99](https://github.com/shkiefer/dash_vtk_unstructured/blob/24bdd651b7be83291421873efda66c0446f74e60/dash_vtk_unstructured.py#L99)


```py
import numpy as np
from pyvista import examples
import pyvista as pv
grid = pv.read('grid.vtu')
arr = grid.cell_data.pop('my_array')
grid.cell_data['Equivalent (von-Mises) Stress (psi)'] = arr.astype(np.float32)
grid.points = grid.points.astype(np.float32)
filename =
grid.save('~/data/Data/fea/kiefer/dataset.vtu')
```

#### PyVista - Load and Plot

With `pyvista>=0.37.0`:

```py
from pyvista import examples
mesh = examples.download_fea_bracket()
mesh.plot()
```
