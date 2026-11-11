# Datasets

## mola_meg128

Dados topográficos de marte coletados pela Mars Global Surveyor.
Eles fazem parte do conjunto MOLA MEG128, que divide a superfície marciana em rasters.
Cada raster é uma matriz de pixels que representa uma região do planeta.

### MEGT - Median Topography - Elevação (I16)
Representa a altitude mediana da superfície em cada pixel,
em metros, relativa ao areoide marciano MOLA.

### MEGR - Mean Radius - Raio Médio (I16)
Representa a distância média entre o centro de Marte e a superfície em cada pixel, em metros codificados com um offset de 3.396.000 m.
`raio = valor + 3396000`

### MEGC - Counts per Bin - Cobertura de Observações (U8)
Indica quantas observações do MOLA foram registradas em cada pixel.

*Arquivos:*
- .img - Dados rasterizados em formato binário
- .lbl - Metadados oficiais no formato PDS3
- .hdr - Cabeçalho ENVI com informações para interpretar o raster.
- .xml - Metadados estruturados em XML.
