# Traspaso: automatización de perfiles desde `resume.json`

Contexto comprimido de una conversación en claude.ai (15 sep 2026) para continuar en Claude Code.
Colócalo en la raíz del repo (o renómbralo a `CLAUDE.md`) junto con `resume.json`.

## 1. Objetivo

Usar un único `resume.json` como fuente de verdad (y "API REST" estática) para mantener
sincronizados automáticamente:

1. **Web de GitHub Pages** (`danielmoralesc.github.io`, Jekyll) → página de CV generada desde el JSON.
2. **README del perfil de GitHub** (`danielmoralesc/danielmoralesc`) → regenerado por GitHub Actions.
3. **ORCID** → subida de publicaciones vía Member API, sin duplicados (clave: DOI).
4. **LinkedIn** → pendiente de explicar (no tiene API pública para editar el perfil personal; solo cabe un proceso semiautomático/manual).

## 2. Usuario

- Daniel Morales Campos. Doctorando en Economía, Empresa y Derecho, Universidad Pública de Navarra (UPNA, Pamplona). Tesis: impacto de la minería del cobre chilena en emisiones de GEI (1840–2024). Directores: Cristián Ducoing Ruiz y Mar Rubio-Varas. Ayuda predoctoral ANDIA (Gobierno de Navarra, 2025–2028).
- También desarrollador web freelance. GitHub: `danielmoralesc`. ORCID: `0000-0002-5581-8542`.
- Preferencias: respuestas completas; contenido académico en inglés británico; conversación en español.
- Herramientas: R + Quarto, Python, Git, Zotero + Better BibTeX (posible fuente BibTeX futura), Obsidian.

## 3. Hallazgos sobre los repositorios

- **Repo local de la web:** `/home/daniel/Desarrollo Web/danielmoralesc.github.io/` (¡ruta con espacio!). Servidor local en `http://0.0.0.0:4000/` → casi seguro **Jekyll** (sin confirmar: revisar `_config.yml`, `Gemfile`, layouts, página de CV actual y workflows existentes).
- **`danielmoralesc/danielmoralesc.github.io` en GitHub:** no accesible públicamente (pide credenciales) → privado o no subido. **Pregunta abierta:** ¿privado a propósito? Pages desde repo privado requiere plan de pago; y el JSON sería público igualmente vía Pages.
- **`danielmoralesc/danielmoralesc`** (repo de perfil): público, rama **`master`** (no `main`), un único `README.md` de junio 2022 (intereses Vue/Nuxt/WordPress, gmail personal). Se sustituirá por el generado.

## 4. Arquitectura propuesta (pendiente de validar contra el repo real)

- `resume.json` vive en el repo de Pages, idealmente en **`_data/resume.json`** → Jekyll lo expone como `site.data.resume` para la página de CV.
- Endpoint público: una página `resume.json` en la raíz con front matter y `{{ site.data.resume | jsonify }}` → `https://danielmoralesc.github.io/resume.json` (valor ya puesto en `meta.canonicalUrl`).
- Workflow en el repo de Pages que, al cambiar el JSON:
  1. valida el JSON;
  2. genera `README.md` y hace **push cross-repo** a `danielmoralesc/danielmoralesc` (rama `master`) → requiere **fine-grained PAT** con `contents: write` solo sobre ese repo (secret, p. ej. `PROFILE_REPO_TOKEN`); el `GITHUB_TOKEN` no puede escribir en otro repo;
  3. (job separado, environment `orcid`) sincroniza ORCID.
- Evitar dos fuentes de verdad: la página de CV de Jekyll debe leer el JSON, no duplicar datos.

## 5. Estado de los entregables

| Pieza | Estado |
|---|---|
| `resume.json` con datos reales | ✅ Movido a `_data/resume.json`; endpoint `/resume.json` (raíz) con `jsonify` verificado en local |
| Plantilla Jekyll de CV desde `_data` | ✅ `_includes/cv-template.html` + `cv-date-range.html`, página `_pages/cv-json.md` en `/cv/` (se borró el `cv.md` de demo) |
| `scripts/generate_readme.py` | ✅ Reescrito para el esquema real; probado (`--check`, validación, DOIs duplicados) |
| Workflow README | ✅ `.github/workflows/profile_readme.yml` cross-repo a `master`, acciones fijadas por SHA; falta crear secret `PROFILE_REPO_TOKEN` |
| `scripts/sync_orcid.py` | ⚠️ Respuesta anterior **cortada** a mitad de `main()`; rehacer completo |
| Workflow `sync_orcid.yml` | ❌ No entregado |
| Nota LinkedIn | ❌ No entregada |

Hallazgos (15 sep 2026): plantilla **Academic Pages** (Jekyll 3.10, `github-pages` 232) casi sin personalizar; servidor local vía `docker compose`. Repo de Pages **privado y sin Pages activado**. Sin commits aún de este trabajo.

## 6. Esquema de `resume.json` (real)

Claves de primer nivel: `meta`, `basics`, `affiliations`, `education`, `publications`,
`researchProjects`, `funding`, `teaching` (vacío), `presentations` (vacío), `projects` (vacío), `skills`.

Convenciones:
- Fechas ISO parciales (`"2024"` o `"2024-01"`); `endDate: null` = actualidad.
- `publications[].type` usa el vocabulario de ORCID (`journal-article`, `conference-poster`, `preprint`…).
- `authors[]`: `{name, orcid?, isSelf?}`; nombre en formato cita (`"Morales-Campos, D."`); `isSelf` → negrita en README.
- `venue`: `name, type, volume, issue, pages, articleNumber, publisher, issn`.
- `originalTitle` y `languageCode` para títulos en idioma original. **Preferencia de Daniel (15 sep 2026):** mostrar siempre el título original primero y la traducción inglesa (`title`) entre corchetes, en web, CV, home, prensa y README; verificar títulos originales en Crossref.
- Opcional `orcidSync: false` para excluir una publicación de ORCID.
- `researchProjects[]`: `code, programme, funder, title, role, startDate, endDate, institution`.
- `basics.citationName`, `basics.supervisors[]` (sin emails).
- `basics.about[]` (12 nov 2026): párrafos en primera persona; el primero va en el hero de la portada (bajo el nombre) y el resto en la sección About. `basics.researchLines[]`: `{title, icon, description, keywords}`. Se retiró `basics.researchPeriod` y su banda 1840–2024 al ampliar el enfoque más allá de la minería.
- README del perfil (12 nov 2026): versión breve, no el CV completo. Secciones: cabecera con badges grandes, *What I work on* (`researchLines[]`, con `emoji` solo para el README), *Now* (tesis en curso, `publications[]` con `status: forthcoming`, `presentations[]` con `status: upcoming`), *Selected publications* (`featured: true`, sin las forthcoming), *Toolbox* (`skills`), *Also on the web* (clave `webDevelopment {summary, keywords}`, que la web Jekyll no muestra) y pie con enlaces al CV.
- `press[]` y `teaching[]` ya en uso; `placeholder: true` marca datos de ejemplo (el generador del README se niega a publicar con ellos).

## 7. Revisiones pendientes del usuario sobre el JSON

1. **Privacidad:** se omitieron teléfono y emails de los directores (no reintroducir).
2. **Títulos posiblemente traducidos** en Macrohistoria, RIVAR e Historia Agraria → confirmar título original y `languageCode` (importa para ORCID). ✅ Historia 396 resuelto (15 sep 2026, vía Crossref): `originalTitle` "Desigualdad regional de la evolución histórica del suicidio en Chile, 1921-2021", `languageCode: es`, publicado 2025-08.
3. **Inferencias a verificar:** puesto "Predoctoral Researcher (ANDIA grant)"; financiador ANID/CONICYT de FONDECYT y Anillos; `skills` (la sección web viene del README de 2022, probablemente desactualizada).
4. **Datos faltantes:** URL de LinkedIn, nivel de inglés, congresos/pósteres, título de la tesis, número de la ayuda ANDIA, ROR de instituciones, si incluir trabajos freelance en `projects`.

## 8. Especificaciones técnicas acordadas

### Generador de README (Python, solo stdlib)
- Determinista: usa `meta.lastModified`, no la fecha de ejecución → solo hay commit si cambia el contenido.
- Validación mínima con mensajes claros; modo `--check` (exit 1 si desactualizado).
- Diseño: cabecera centrada con badges de perfiles (shields.io + Simple Icons; color de logo según luminancia; LinkedIn sin logo porque Simple Icons lo retiró); secciones: sobre mí + intereses, posición actual, stack con badges, publicaciones en tabla (año, título enlazado al DOI, autores con el propio en negrita y *et al.* garantizando que aparezca, revista con volumen/número/páginas, badge DOI), proyectos de investigación, trayectoria, formación, financiación, pie con enlace al JSON.
- Etiquetas de interfaz en un diccionario `LABELS` (probablemente en inglés para el perfil).
- Escapar `|` en celdas; `[texto](<url>)` para DOIs con paréntesis; escapar `-`/`_` en badges estáticos.

### Workflow README
- `on.push.paths` limitado al JSON, al script y al propio workflow; `workflow_dispatch`; `concurrency` con `cancel-in-progress`.
- Detectar cambios con `git status --porcelain` (cubre archivos nuevos); commit como `github-actions[bot]`.
- Recomendación: fijar acciones por SHA.

### ORCID
- **La Public API es solo lectura.** Escribir exige **Member API** (preguntar a Biblioteca/Servicio de Investigación de la UPNA; España tiene consorcio ORCID). Desarrollar en **sandbox** (por defecto en el script).
- Token de **3 patas** con scope `/activities/update` (no client credentials): authorize URL → `code` → `POST /oauth/token` con `grant_type=authorization_code`; devuelve `access_token`, `refresh_token`, `orcid`, validez ~20 años.
- Secrets en environment `orcid`: `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`, `ORCID_ACCESS_TOKEN`, `ORCID_REFRESH_TOKEN` (opcional); variables `ORCID_ENV` (`sandbox`|`production`), `ORCID_ID`. Flags `ORCID_UPDATE_EXISTING`, `DRY_RUN`.
- Endpoints v3.0 (`https://api.orcid.org/v3.0`, sandbox `https://api.sandbox.orcid.org/v3.0`), media type `application/vnd.orcid+json`:
  - `GET /{orcid}/works` → indexar por DOI normalizado (minúsculas, sin `https://doi.org/`/`doi:`), solo `relationship: self`.
  - `POST /{orcid}/work` → 201, put-code al final de `Location`.
  - `PUT /{orcid}/work/{put-code}` → solo trabajos cuyo `source-client-id` == tu client id; el body incluye `put-code`.
- Lógica anti-duplicados: DOI ausente → POST; presente y fuente propia → omitir o PUT si `UPDATE_EXISTING`; presente con otra fuente (Crossref, Scopus, manual) → omitir; `409` en POST → tratar como duplicado. Detectar DOIs repetidos dentro del JSON. Sin DOI → omitir con aviso.
- Payload del work: `title` (+ subtítulo), `type` validado contra vocabulario ORCID (fallback `other`), `external-ids` (DOI `self`; ISSN `part-of`), `url`, `contributors` (`first`/`additional`, `author`, `contributor-orcid` si hay), `journal-title`, `publication-date` (mes/día con 2 dígitos), `short-description`, `language-code`, `citation` BibTeX.
- Robustez: reintentos con backoff en 429/5xx y `Retry-After`; renovación de token ante 401 con `::add-mask::`; errores fatales 401/403/404 (404 suele ser mezclar sandbox/producción); anotaciones `::error::`/`::warning::`; resumen en `GITHUB_STEP_SUMMARY`; exit codes 0/1/2.
- Nota: los 6 artículos tienen DOI Crossref → probablemente ya estén en ORCID vía auto-update de Crossref; el script servirá sobre todo para trabajos futuros.

## 9. Próximos pasos en Claude Code

1. Inspeccionar el repo local: generador (Jekyll/versión), `_config.yml`, `Gemfile`, layouts/includes, página de CV actual, `.github/workflows`, rama y remoto.
2. Resolver con Daniel las revisiones de la sección 7 y la pregunta sobre visibilidad del repo.
3. Mover `resume.json` a `_data/` y crear el endpoint `/resume.json`.
4. Reescribir la página de CV de Jekyll para que lea `site.data.resume`.
5. Reescribir `generate_readme.py` para el esquema real + workflow cross-repo.
6. Escribir `sync_orcid.py` completo + `sync_orcid.yml` (sandbox primero).
7. Explicar la opción viable para LinkedIn.
