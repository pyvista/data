### Dataset from GGG-BenchmarkSfM

The datasets in this directory were downloaded from [GGG-BenchmarkSfM: Dataset for Benchmarking Close-range SfM Software Performance under Varying Capturing Conditions](https://data.mendeley.com/datasets/bzxk2n78s9/4)

The datasets were converted to the VTP format with float32 precision.

#### `blackVase.off`

```py
import pyvista as pv

dataset = pv.read('Objects and Environments Data/BlackVase/blackVase.off')
surf = dataset.extract_surface()
surf.clear_data()
surf.points = surf.points.astype(np.float32)
surf.save('blackVase.vtp')
```

#### `Angle.off`

This was a very large dataset and was decimated to reduce the file size to
below 50 MB to avoid GitHub's file size warnings.

```py
import numpy as np
import pyvista as pv

# reduce the size of a mesh
mesh = pv.read('Objects and Environments Data/Angel/Angel.off')
surf = mesh.extract_surface()
surf.clear_data()
dec_surf = surf.decimate(0.65)
dec_surf.points = dec_surf.points.astype(np.float32)
dec_surf.save('/home/alex/python/pyvista/data/Data/ivan-nikolov/Angle.vtp')
```

#### `birdBath.off`

Automate the zipping of the vtp.

```py
import os
import numpy as np
import pyvista as pv

# reduce the size of a mesh
base_name = 'birdBath'
mesh = pv.read(f'Objects and Environments Data/BirdBath/{base_name}.off')
surf = mesh.extract_surface()
surf.clear_data()

# 1.8 M points for sub 50M when compressed
dec_surf = surf.decimate((surf.n_points - 1_800_000)/surf.n_points)
dec_surf.points = dec_surf.points.astype(np.float32)
out_path = '/home/alex/python/pyvista/data/Data/ivan-nikolov/'
filename_vtp = os.path.join(out_path, f'{base_name}.vtp')
dec_surf.save(filename_vtp)
filename_zip = os.path.join(out_path, f'{base_name}.zip')
os.system(f'zip {filename_zip} {filename_vtp}')
os.remove(filename_vtp)
if os.path.getsize(filename_zip) > 5E7:
    print('Filename exceeds 50 MB!')
```

#### `plasticVase.off`

Deal with the additional wrinkle that the dataset hasn't been cleaned up and
there are a few separated components.

```py
import os
import numpy as np
import pyvista as pv

# reduce the size of a mesh
datadir = 'PlasticVase'
base_name = 'plasticVase'
mesh = pv.read(f'/home/alex/Downloads/bzxk2n78s9-4/Objects and Environments Data/{datadir}/{base_name}.off')
surf = mesh.extract_surface()
surf.clear_data()

# 1.8 M points for sub 50M when compressed
tgt_points = 1_800_000
if surf.n_points > tgt_points:
    dec_surf = surf.decimate((surf.n_points - 1_800_000)/surf.n_points)
    dec_surf.points = dec_surf.points.astype(np.float32)
else:
    dec_surf = surf

# use only the largest body
bodies = dec_surf.split_bodies()
idx = np.argmax([body.n_points for body in bodies])
dec_surf = bodies[idx].extract_surface()

out_path = '/home/alex/python/pyvista/data/Data/ivan-nikolov/'
filename_vtp = os.path.join(out_path, f'{base_name}.vtp')
dec_surf.save(filename_vtp)
filename_zip = os.path.join(out_path, f'{base_name}.zip')
os.system(f'zip {filename_zip} {filename_vtp} -j')
os.remove(filename_vtp)
if os.path.getsize(filename_zip) > 5E7:
    print('Filename exceeds 50 MB!')

```


### License

The original datasets are under CC BY 4.0, which states:

The files associated with this dataset are licensed under a Creative Commons
Attribution 4.0 International license.
What does this mean?

You can share, copy and modify this dataset so long as you give appropriate
credit, provide a link to the [CC BY
license](https://creativecommons.org/licenses/by/4.0/), and indicate if changes
were made, but you may not do so in a way that suggests the rights holder has
endorsed you or your use of the dataset. Note that further permission may be
required for any content within the dataset that is identified as belonging to
a third party.
