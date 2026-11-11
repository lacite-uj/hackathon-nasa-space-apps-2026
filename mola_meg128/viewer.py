
import numpy as np
import xarray as xr
import pyvista as pv

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ZARR_PATH = BASE_DIR / "database.zarr"

TILE_HEIGHT = 5632
TILE_WIDTH = 11520

# Um pixel a cada 32 pixels originais.
STEP = 32

LATITUDES = ["88n", "44n", "00n", "44s"]
LONGITUDES = ["000", "090", "180", "270"]

MARS_RADIUS = 3_396_000.0
VERTICAL_SCALE = 5.0

# Resolução angular dos dados reduzidos.
RESOLUTION = 128 / STEP

H = TILE_HEIGHT // STEP
W = TILE_WIDTH // STEP

if not ZARR_PATH.exists():
    raise FileNotFoundError(f"Zarr não encontrado: {ZARR_PATH}")

world = np.full(
    (H * len(LATITUDES), W * len(LONGITUDES)),
    np.nan,
    dtype=np.float32
)

print("Zarr:", ZARR_PATH)

# Montagem do mosaico.
for row, latitude in enumerate(LATITUDES):
    for col, longitude in enumerate(LONGITUDES):

        tile = latitude + longitude
        print(f"Carregando {tile}...")

        with xr.open_zarr(
            str(ZARR_PATH),
            group=tile,
            consolidated=False
        ) as ds:

            elevation = ds["elevation_m"].isel(
                line=slice(None, None, STEP),
                sample=slice(None, None, STEP)
            ).values.astype(np.float32)

        # Evita problemas caso a dimensão real seja diferente.
        h, w = elevation.shape

        y0 = row * H
        x0 = col * W

        world[
            y0:y0 + h,
            x0:x0 + w
        ] = elevation

print("Mosaico montado:", world.shape)

# Coordenadas geográficas.
lat = 88 - (np.arange(world.shape[0]) + 0.5) / RESOLUTION
lon = (np.arange(world.shape[1]) + 0.5) / RESOLUTION

lon_grid, lat_grid = np.meshgrid(lon, lat)

lat_rad = np.radians(lat_grid)
lon_rad = np.radians(lon_grid)

# Raio com exagero vertical.
radius = MARS_RADIUS + world * VERTICAL_SCALE

# Coordenadas cartesianas.
x = radius * np.cos(lat_rad) * np.cos(lon_rad)
y = radius * np.cos(lat_rad) * np.sin(lon_rad)
z = radius * np.sin(lat_rad)

# PyVista StructuredGrid.
grid = pv.StructuredGrid()

grid.dimensions = (
    world.shape[1],
    world.shape[0],
    1
)

points = np.column_stack((
    x.ravel(order="C"),
    y.ravel(order="C"),
    z.ravel(order="C")
))

grid.points = points

# A elevação será utilizada para colorir a superfície.
grid.point_data["elevation"] = world.ravel(order="C")

# Máscara de validade.
valid = np.isfinite(world)

if not np.any(valid):
    raise RuntimeError("Nenhum dado de elevação válido foi encontrado.")

vmin, vmax = np.percentile(world[valid], [2, 98])

# Configuração da visualização.
plotter = pv.Plotter(window_size=(1440, 1000))

plotter.add_mesh(
    grid,
    scalars="elevation",
    cmap="terrain",
    clim=(vmin, vmax),
    nan_color="black",
    show_scalar_bar=True,
    scalar_bar_args={
        "title": "Elevação (m)",
        "vertical": True,
        "title_font_size": 18,
        "label_font_size": 12,
    },
    smooth_shading=True,
    show_edges=False
)

plotter.add_text(
    "Marte - MOLA MEG128",
    position="upper_left",
    font_size=16
)

plotter.set_background("#10141c")
plotter.add_axes()
plotter.enable_anti_aliasing()

plotter.camera_position = "xy"
plotter.camera.zoom(1.2)

plotter.show()
