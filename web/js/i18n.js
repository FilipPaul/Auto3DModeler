// Czech / English. The app is written in English; this layer translates what is on the page as it
// appears (text, tooltips, placeholders — also panels, dialogs and messages built later), by exact text
// or by pattern (texts with values in them). Switching is live: originals are kept on the nodes.
// Not translated: the user's own text (chat, project name, inputs) and numbers on dimension labels.

const KEY = 'auto3d-lang';
let lang = 'en';
try { lang = localStorage.getItem(KEY) || ''; } catch { /* private mode */ }
if (lang !== 'en' && lang !== 'cs') lang = (navigator.language || '').toLowerCase().startsWith('cs') ? 'cs' : 'en';

// ---------------------------------------------------------------------------- exact texts
const CS = {
  // top bar
  'No drawing loaded': 'Není otevřen žádný výkres',
  'Open PDF': 'Otevřít PDF', 'Open picture': 'Otevřít obrázek', 'Open CAD / 3D': 'Otevřít CAD / 3D',
  'Sample drawing': 'Ukázkový výkres', 'Open project': 'Otevřít projekt', 'Save project': 'Uložit projekt', 'Export ▾': 'Export ▾',
  'Trace the outline of an object in a picture (cookie cutters, shapes…)': 'Obkreslit obrys předmětu na obrázku (vykrajovátka, tvary…)',
  'DXF / DWG drawings (an outline in real size) and STL / OBJ / STEP 3D files': 'Výkresy DXF / DWG (obrys ve skutečné velikosti) a 3D soubory STL / OBJ / STEP',
  'Load initial draft.pdf': 'Načíst initial draft.pdf',
  'STL — 3D printing, whole part (mm)': 'STL — 3D tisk, celý díl (mm)', 'STEP — CAD solid (mm)': 'STEP — CAD těleso (mm)',
  'GLB — 3D preview (colours)': 'GLB — 3D náhled (barvy)',
  // left tabs
  Dimensions: 'Rozměry', Checks: 'Kontroly', Drawing: 'Výkres', '✨ AI': '✨ AI',
  'Tell Claude what to make — it works on the part in the app': 'Řekněte Claudovi, co vyrobit — pracuje přímo na dílu v aplikaci',
  'Open a PDF drawing — or a picture to trace its outline — to start.': 'Začněte otevřením výkresu PDF — nebo obrázku, ze kterého se obkreslí obrys.',
  'Undo every change: values, added dimensions and promoted references': 'Vrátit všechny změny: hodnoty, přidané kóty a povýšené referenční kóty',
  '↺ Restore drawing defaults': '↺ Obnovit podle výkresu', 'Matches the drawing': 'Odpovídá výkresu',
  'Needs your attention': 'Vyžaduje pozornost', 'Added by you': 'Přidané vámi', Assumptions: 'Předpoklady',
  'Reference (driven by others)': 'Referenční (určené ostatními)', 'not in drawing': 'není ve výkresu',
  'from the drawing': 'z výkresu', 'original value': 'původní hodnota', 'Use this value': 'Použít tuto hodnotu',
  'Make driving': 'Udělat řídící', Remove: 'Odebrat', 'Remove this dimension': 'Odebrat tuto kótu', Decrease: 'Snížit', Increase: 'Zvýšit',
  'Click to rename': 'Klikněte pro přejmenování', 'Choose which dimension becomes a reference instead:': 'Vyberte, která kóta se místo toho stane referenční:',
  Apply: 'Použít', 'Dimensions restored to the drawing defaults.': 'Rozměry obnoveny podle výkresu.',
  'part size': 'velikost dílu', 'from drawing': 'z výkresu', 'set by you': 'nastaveno vámi', 'added by you': 'přidáno vámi',
  estimated: 'odhad', default: 'výchozí', reference: 'referenční', assumed: 'předpoklad', conflict: 'konflikt',
  'Show the drawing large, with zoom and pan': 'Zobrazit výkres velký, s přiblížením a posunem', '⤢ Enlarge': '⤢ Zvětšit',
  'Open the outline editor with the outline the part is made from': 'Otevřít editor obrysu s obrysem, ze kterého je díl vyroben',
  'Open the outline editor with the outline this part is made from': 'Otevřít editor obrysu s obrysem, ze kterého je tento díl vyroben',
  '✎ Edit outline': '✎ Upravit obrys', '✎ Edit outline…': '✎ Upravit obrys…', 'No drawing.': 'Žádný výkres.', 'Click to enlarge': 'Klikněte pro zvětšení',
  outline: 'obrys', dimension: 'kóta', problem: 'problém',
  'A 3D file has no drawing — see the 3D view.': '3D soubor nemá výkres — viz 3D pohled.',
  // 3D toolbar
  'Undo (Ctrl+Z)': 'Zpět (Ctrl+Z)', 'Redo (Ctrl+Y / Ctrl+Shift+Z)': 'Znovu (Ctrl+Y / Ctrl+Shift+Z)',
  Iso: 'Izo', Front: 'Zepředu', Back: 'Zezadu', Side: 'Z boku', 'Edges only': 'Jen hrany',
  'Add a dimension between two edges / corners / points (D) — as many as you like': 'Přidat kótu mezi dvěma hranami / rohy / body (D) — kolik chcete',
  '＋ Dimension': '＋ Kóta', 'Measure between two points on the part (M)': 'Měřit mezi dvěma body na dílu (M)', '📏 Measure': '📏 Měřit',
  'Show the part unbent (to edit masks and dimensions)': 'Zobrazit díl neohnutý (pro úpravu masek a kót)', 'Flat view': 'Rovný pohled',
  'Building 3D…': 'Sestavuji 3D…', 'Stop this (the part stays as it was)': 'Zastavit (díl zůstane, jak byl)', Cancel: 'Zrušit', 'Cancelling…': 'Ruším…',
  "Drop a PDF, DXF / DWG, STL / OBJ / STEP or a picture here (Shift = trace a picture's outline)": 'Přetáhněte sem PDF, DXF / DWG, STL / OBJ / STEP nebo obrázek (Shift = obkreslit obrys obrázku)',
  'Building the part': 'Sestavuji díl', 'Building the 3D view': 'Sestavuji 3D pohled', 'Starting…': 'Spouštím…',
  // right tabs
  Part: 'Díl', '3D design': '3D design', '3D print': '3D tisk',
  'The part: where it comes from, 2D shapes on its profile and 3D objects added to it': 'Díl: odkud pochází, 2D tvary na jeho profilu a přidané 3D objekty',
  '＋ Grid': '＋ Mřížka', '＋ Shape': '＋ Tvar', '＋ Image': '＋ Obrázek', '＋ Outline': '＋ Obrys',
  'Trace an object in a picture with the outline editor and use its outline as the mask (emboss / engrave / cut it into the part)': 'Obkreslit předmět na obrázku editorem obrysu a použít obrys jako masku (vytlačit / vyrýt / prořezat do dílu)',
  'Snap dragged masks to': 'Přichytit tažené masky na', 'Snap step': 'Krok přichycení', 'Bend the part': 'Ohnout díl',
  'Click on the part to place a fold line': 'Klikněte na díl pro umístění linie ohybu', '＋ Fold line': '＋ Linie ohybu',
  'Bend the whole length into an arc or tube': 'Ohnout celou délku do oblouku nebo trubky', '＋ Roll': '＋ Stočit', Colours: 'Barvy', 'Part / design': 'Díl / design',
  // part panel
  'Made from the drawing': 'Vyrobeno z výkresu', 'Imported 3D file': 'Importovaný 3D soubor', 'Outline from the drawing': 'Obrys z výkresu', 'Outline from': 'Obrys z',
  'Keep aspect ratio (width ↔ height)': 'Zachovat poměr stran (šířka ↔ výška)', 'Mirror outline': 'Zrcadlit obrys',
  'Open the outline editor with this outline (your edit and hints are kept) — edit it or pick another one; size, shapes and objects stay': 'Otevřít editor obrysu s tímto obrysem (vaše úpravy a nápovědy zůstanou) — upravte ho nebo vyberte jiný; velikost, tvary a objekty zůstanou',
  'Flip left ↔ right. A cookie cutter is turned over to use it, so mirror it if the cookie must look exactly like the picture.': 'Převrátit vlevo ↔ vpravo. Vykrajovátko se při použití otáčí, zrcadlete ho, pokud musí perník vypadat přesně jako obrázek.',
  'Outline clean-up': 'Úprava obrysu', 'Fill holes': 'Vyplnit díry', 'Close gaps (mm)': 'Uzavřít mezery (mm)', 'Round corners (mm)': 'Zaoblit rohy (mm)',
  'Simplify (mm)': 'Zjednodušit (mm)', Pieces: 'Kusy', 'Keep all': 'Ponechat vše', 'Largest only': 'Jen největší', 'Convex hull': 'Konvexní obal', 'Reset clean-up': 'Zrušit úpravy',
  'Applied to the traced outline in mm. Cookie cutters cannot cut notches narrower than about twice the wall — close or round them here.': 'Použije se na obkreslený obrys v mm. Vykrajovátka neprořežou zářezy užší než asi dvojnásobek stěny — uzavřete nebo zaoblete je zde.',
  Make: 'Vyrobit', 'Cookie cutter': 'Vykrajovátko', 'Solid shape': 'Plný tvar', Custom: 'Vlastní',
  'Printed flange-down; the inside of the wall is exactly on the outline (+ clearance), so cookies come out at the size you set. The cutting edge is the thinner top part of the wall.': 'Tiskne se límcem dolů; vnitřek stěny leží přesně na obrysu (+ vůle), takže perníky mají zadanou velikost. Řezná hrana je tenčí horní část stěny.',
  'The whole shape extruded — e.g. the cookie itself, a plaque or a base. Design layers (right tab) can emboss or engrave its top.': 'Celý tvar vytažený do výšky — např. samotný perník, destička nebo podstavec. Vrstvy designu (pravá záložka) mohou jeho horní plochu vytlačit nebo vyrýt.',
  'Objects are built from the top of the list down: each one adds (∪), removes (−) or keeps only the overlap (∩) with everything above it.': 'Objekty se sestavují odshora seznamu: každý přidá (∪), odebere (−) nebo ponechá jen průnik (∩) se vším nad ním.',
  'Wall thickness (mm)': 'Tloušťka stěny (mm)', 'Total height (mm)': 'Celková výška (mm)', 'Cutting edge (mm)': 'Řezná hrana (mm)', 'Edge height (mm)': 'Výška hrany (mm)',
  'Flange width (mm)': 'Šířka límce (mm)', 'Flange thickness (mm)': 'Tloušťka límce (mm)', 'Clearance (mm)': 'Vůle (mm)', 'Thickness (mm)': 'Tloušťka (mm)', 'Grow / shrink (mm)': 'Zvětšit / zmenšit (mm)',
  'Edit as 3D objects →': 'Upravit jako 3D objekty →', 'Edit as 3D objects': 'Upravit jako 3D objekty',
  'Switch to Custom with the objects this preset is made of, to add holes, handles, extra offsets…': 'Přepnout na Vlastní s objekty, ze kterých se předvolba skládá — pro přidání děr, úchytů, dalších odsazení…',
  '3D objects added to the part': '3D objekty přidané k dílu', '3D objects': '3D objekty',
  'Booleaned onto the part above, from the top of the list down (a hole = Subtract).': 'Kombinují se s dílem výše, odshora seznamu (díra = Odečíst).',
  '＋ Cylinder': '＋ Válec', '＋ Box': '＋ Kvádr', '＋ Bar': '＋ Tyč', '＋ Text': '＋ Text', '＋ Profile': '＋ Profil', '＋ Profile band': '＋ Pás profilu',
  '＋ Footprint': '＋ Půdorys', '＋ Footprint band': '＋ Pás půdorysu', '＋ Outline band': '＋ Pás obrysu', '＋ Circle': '＋ Kruh', '＋ Rectangle': '＋ Obdélník', '＋ Line': '＋ Čára', '＋ Hole': '＋ Díra',
  'Raised or cut text, e.g. a name on the flange': 'Vystouplý nebo vyřezaný text, např. jméno na límci',
  'Letters joined to (or cut from) the outline': 'Písmena připojená k obrysu (nebo z něj vyříznutá)', 'A round hole near the top — e.g. to hang an ornament': 'Kulatá díra u horního okraje — např. na pověšení ozdoby',
  'No objects yet — click ＋ and then where it goes on the part.': 'Zatím žádné objekty — klikněte na ＋ a pak na místo na dílu.',
  'None — drag shapes on the part once added.': 'Žádné — přidané tvary lze táhnout po dílu.', 'No objects yet.': 'Zatím žádné objekty.',
  '— a cookie cutter wall follows them too': '— stěna vykrajovátka je také sleduje',
  Include: 'Zahrnout', Duplicate: 'Duplikovat', 'Move up': 'Posunout nahoru', 'Move down': 'Posunout dolů', Delete: 'Smazat',
  Name: 'Název', Operation: 'Operace', 'Made from': 'Vyrobeno z', Region: 'Oblast', 'Filled (offset)': 'Vyplněno (odsazení)', 'Band between offsets': 'Pás mezi odsazeními',
  'Offsets in / out': 'Odsazení dovnitř / ven', 'Offset (mm)': 'Odsazení (mm)', 'Offsets are measured from the outline: + outwards, − inwards.': 'Odsazení se měří od obrysu: + ven, − dovnitř.',
  'Start x / y': 'Začátek x / y', 'End x / y': 'Konec x / y', 'Width (mm)': 'Šířka (mm)', 'Round ends': 'Kulaté konce', 'Centre x / y': 'Střed x / y',
  'Diameter w / h': 'Průměr š / v', 'Size w / h': 'Velikost š / v', 'Rotation °': 'Natočení °', 'Ring width': 'Šířka prstence',
  'Ring width 0 = filled; > 0 = only a ring (tube / frame) of that width.': 'Šířka prstence 0 = plný; > 0 = jen prstenec (trubka / rám) dané šířky.',
  'Bottom / top z': 'Spodní / horní z', '⌖ = click on the part: a face gives its height, corners and edges snap.': '⌖ = klikněte na díl: plocha dá svou výšku, rohy a hrany se přichytí.',
  'Pick the centre': 'Vybrat střed', 'Pick the start point': 'Vybrat počáteční bod', 'Pick the end point': 'Vybrat koncový bod',
  'Pick the bottom height (extrude from)': 'Vybrat spodní výšku (vytáhnout od)', 'Pick the top height (extrude to)': 'Vybrat horní výšku (vytáhnout do)',
  Text: 'Text', Font: 'Písmo', Bold: 'Tučně', 'Letter height': 'Výška písma', Shape: 'Tvar', 'Circle / ellipse': 'Kruh / elipsa', Rectangle: 'Obdélník',
  '∪ Add (union)': '∪ Přidat (sjednocení)', '− Subtract': '− Odečíst', '∩ Intersect': '∩ Průnik', '∪ add': '∪ přidat', '− cut': '− řez', '∩ overlap': '∩ průnik',
  '∪ Add to outline': '∪ Přidat k obrysu', '− Cut from outline': '− Vyříznout z obrysu',
  Outline: 'Obrys', Profile: 'Profil', Footprint: 'Půdorys', 'Circle / cylinder': 'Kruh / válec', 'Rectangle / box': 'Obdélník / kvádr', 'Line / bar': 'Čára / tyč',
  Cylinder: 'Válec', Box: 'Kvádr', Bar: 'Tyč', Circle: 'Kruh', Line: 'Čára', Hole: 'Díra', 'Profile band': 'Pás profilu', 'Outline band': 'Pás obrysu',
  Flange: 'Límec', Wall: 'Stěna', 'Cutting edge': 'Řezná hrana',
  'Bold sans': 'Tučné bezpatkové', Sans: 'Bezpatkové', Serif: 'Patkové', Comic: 'Komiksové', Script: 'Psací', Mono: 'Neproporcionální',
  'Up is': 'Nahoře je', '+Z (as in the file)': '+Z (jako v souboru)', '−Z (upside down)': '−Z (vzhůru nohama)', Turn: 'Otočit', Mirror: 'Zrcadlit', 'Slice height': 'Výška řezu',
  'Type some text first.': 'Nejprve napište text.', 'This text produced no outline.': 'Z tohoto textu nevznikl žádný obrys.',
  // design layers
  'No design layers yet. Add a grid, a shape or an image —': 'Zatím žádné vrstvy designu. Přidejte mřížku, tvar nebo obrázek —',
  'each can be embossed, engraved or cut through.': 'každý lze vytlačit, vyrýt nebo prořezat.',
  'Show / include in export': 'Zobrazit / zahrnout do exportu', 'Delete layer': 'Smazat vrstvu', Face: 'Plocha', 'Front (top)': 'Přední (horní)', 'Back (bottom)': 'Zadní (spodní)',
  'Mask — where it applies': 'Maska — kde se použije', Mask: 'Maska', 'Invert mask': 'Invertovat masku', Fill: 'Výplň', Use: 'Použít',
  'Emboss (raise)': 'Vytlačit (zvednout)', 'Engrave (cut in)': 'Vyrýt (zahloubit)', 'Cut through': 'Prořezat', 'Guide only (no geometry)': 'Jen vodítko (bez geometrie)',
  'Whole face': 'Celá plocha', Ellipse: 'Elipsa', 'Image / logo': 'Obrázek / logo', Solid: 'Plná',
  'Grid — square': 'Mřížka — čtvercová', 'Grid — rectangular': 'Mřížka — obdélníková', 'Grid — diagonal / diamond': 'Mřížka — diagonální / kosočtverec',
  'Grid — triangular (isometric)': 'Mřížka — trojúhelníková (izometrická)', 'Hexagonal (honeycomb)': 'Šestiúhelníková (plástev)', 'Brick / running bond': 'Cihly / vazba',
  'Columns / slats': 'Sloupky / lamely', Waves: 'Vlny', Zigzag: 'Cikcak', 'Chevron / herringbone': 'Rybí kost', 'Fish scales': 'Rybí šupiny',
  'Voronoi (organic cells)': 'Voronoi (organické buňky)', 'Contour (follows the outline)': 'Kontura (sleduje obrys)', Spiral: 'Spirála', 'Radial (rings + rays)': 'Radiální (kruhy + paprsky)',
  'Shapes — dots': 'Tvary — tečky', 'Shapes — circles': 'Tvary — kroužky', 'Shapes — checkerboard': 'Tvary — šachovnice', 'Shapes — stars': 'Tvary — hvězdy', 'Shapes — crosses': 'Tvary — křížky',
  Grid: 'Mřížka', Logo: 'Logo', '↑ emboss': '↑ vytlačit', '↓ engrave': '↓ vyrýt', '⊘ cut': '⊘ prořez', '┄ guide': '┄ vodítko',
  'Filled shapes': 'Vyplněné tvary', 'Shape outlines (ribs)': 'Obrysy tvarů (žebra)', 'Pattern lines (ribs)': 'Čáry vzoru (žebra)', 'Cells between lines': 'Buňky mezi čarami',
  'Shape size ×': 'Velikost tvaru ×', 'Amplitude ×': 'Amplituda ×', Randomness: 'Náhodnost', Seed: 'Semínko', 'Star points': 'Cípy hvězdy', Rays: 'Paprsky',
  Origin: 'Počátek', Centre: 'Střed', 'Bottom-left corner': 'Levý dolní roh',
  'Reopen the outline editor with this mask (your edit and hints are kept)': 'Znovu otevřít editor obrysu s touto maskou (úpravy a nápovědy zůstanou)',
  // bends
  'Apply this bend': 'Použít tento ohyb', 'Remove bend': 'Odebrat ohyb', Roll: 'Stočení', '◠ roll': '◠ stočení', '∧ fold': '∧ ohyb', '∨ fold': '∨ ohyb', Type: 'Typ',
  'Fold at a line': 'Ohyb podle linie', 'Roll the whole length': 'Stočit celou délku', 'Front outside (roof ∧ / tube)': 'Přední strana vně (střecha ∧ / trubka)',
  'Front inside (gutter ∨)': 'Přední strana uvnitř (žlab ∨)', 'Fold line': 'Linie ohybu', 'Vertical (bends left–right)': 'Svislá (ohýbá zleva doprava)',
  'Horizontal (bends up–down)': 'Vodorovná (ohýbá shora dolů)', 'Angle °': 'Úhel °', 'Click on the part to place the fold line.': 'Klikněte na díl pro umístění linie ohybu.',
  'Switched to Flat view to place the fold line.': 'Přepnuto na rovný pohled pro umístění linie ohybu.',
  // dimension tool
  'Same position': 'Stejná poloha', 'Measure the other direction': 'Měřit v druhém směru', Value: 'Hodnota', 'Add dimension': 'Přidat kótu',
  'Pick the first edge or corner (Esc to cancel)': 'Vyberte první hranu nebo roh (Esc zruší)', 'Click on an edge or a corner of the part.': 'Klikněte na hranu nebo roh dílu.',
  'Pick the second edge or corner — the click position sets where the dimension is drawn': 'Vyberte druhou hranu nebo roh — místo kliknutí určí, kde se kóta vykreslí',
  'Pick two parallel edges (or corners) to measure between.': 'Vyberte dvě rovnoběžné hrany (nebo rohy), mezi kterými se měří.', 'Enter a positive number.': 'Zadejte kladné číslo.',
  '✓ set': '✓ nastaveno', '? missing': '? chybí', 'Switched to Flat view to pick edges.': 'Přepnuto na rovný pohled pro výběr hran.',
  'Dimension added — edit it like any other.': 'Kóta přidána — upravujte ji jako ostatní.', 'Delete this dimension': 'Smazat tuto kótu',
  'This dimension comes from the drawing and drives the part — it cannot be deleted.': 'Tato kóta pochází z výkresu a řídí díl — nelze ji smazat.',
  // measure
  'Switch to Flat view to measure.': 'Pro měření přepněte na rovný pohled.', 'the dimension': 'kóty', 'the measurement': 'měření',
  'Cylinder / boss': 'Válec / výstupek', Top: 'Horní', Bottom: 'Spodní', First: 'První', Picked: 'Vybráno', Second: 'Druhý', Point: 'Bod',
  Distance: 'Vzdálenost', 'Distance (centres)': 'Vzdálenost (středů)', radius: 'poloměr', centre: 'střed', depth: 'hloubka', height: 'výška', area: 'plocha', perimeter: 'obvod',
  'Add as': 'Přidat jako', 'Keep as dimension': 'Ponechat jako kótu', 'New dimension': 'Nová kóta', Measure: 'Měření', 'Another dimension': 'Další kóta', 'Measure again': 'Měřit znovu',
  'Click a second point to measure a distance (centre to centre with holes / cylinders).': 'Klikněte na druhý bod pro změření vzdálenosti (mezi středy u děr / válců).',
  Close: 'Zavřít', 'Close (Esc)': 'Zavřít (Esc)', 'top face': 'horní plocha', 'bottom face': 'spodní plocha', corner: 'roh', edge: 'hrana', wall: 'stěna',
  'Click on the part.': 'Klikněte na díl.', 'Switch to Flat view to pick on the part.': 'Pro výběr na dílu přepněte na rovný pohled.',
  'The two points are the same along that direction.': 'Oba body jsou v tomto směru stejné.',
  'Dimension added — type a value to scale the part to it.': 'Kóta přidána — zadejte hodnotu a díl se na ni přeškáluje.',
  'Dimension added (reference — the drawing drives the part).': 'Kóta přidána (referenční — díl řídí výkres).',
  // toasts / loading
  'Cancelled — the part is back to its last state.': 'Zrušeno — díl je zpět v posledním stavu.', 'Please enter a number.': 'Zadejte číslo.',
  'No part outline could be recognised in this PDF — see Checks.': 'V tomto PDF se nepodařilo rozpoznat obrys dílu — viz Kontroly.',
  'Project loaded.': 'Projekt načten.', 'All dimensions read successfully.': 'Všechny rozměry úspěšně načteny.', 'Outline applied to the part.': 'Obrys použit na díl.',
  'Outline loaded — choose what to make in the Part tab, set the real size in Dimensions.': 'Obrys načten — v záložce Díl vyberte, co vyrobit, skutečnou velikost nastavte v Rozměrech.',
  '3D file imported — orientation, scale and added objects are in the Part tab.': '3D soubor importován — orientace, měřítko a přidané objekty jsou v záložce Díl.',
  'Open a drawing or a picture first — the outline is added to that part.': 'Nejprve otevřete výkres nebo obrázek — obrys se přidá k tomuto dílu.',
  'Outline added as a design layer — click where it goes, then choose emboss / engrave / cut through.': 'Obrys přidán jako vrstva designu — klikněte, kam patří, a zvolte vytlačit / vyrýt / prořezat.',
  'Layer outline updated.': 'Obrys vrstvy aktualizován.', 'Please drop a PDF, DXF / DWG, STL / OBJ / STEP or a picture.': 'Přetáhněte PDF, DXF / DWG, STL / OBJ / STEP nebo obrázek.',
  'Load a drawing first.': 'Nejprve načtěte výkres.', 'No shape found in the image (use a dark logo on a light or transparent background).': 'V obrázku nebyl nalezen tvar (použijte tmavé logo na světlém nebo průhledném pozadí).',
  'Image traced — click where it goes on the part, then choose emboss / engrave / cut.': 'Obrázek obkreslen — klikněte, kam na díl patří, a zvolte vytlačit / vyrýt / prořezat.',
  'Not an Auto3DModeler project file.': 'Toto není soubor projektu Auto3DModeler.', 'Import cancelled.': 'Import zrušen.',
  'Outline traced from a picture — set its real size in Dimensions.': 'Obrys obkreslený z obrázku — skutečnou velikost nastavte v Rozměrech.',
  'No open problems.': 'Žádné otevřené problémy.', 'Set the flagged values to resolve them.': 'Nastavte označené hodnoty a vyřešte je.',
  'Auto3DModeler project': 'Projekt Auto3DModeler', 'STL 3D model': '3D model STL', 'STEP CAD model': 'CAD model STEP', 'GLB 3D preview': '3D náhled GLB', 'ZIP of pieces': 'ZIP s díly',
  'cookie cutter': 'vykrajovátka', solid: 'plného tvaru',
  // lightbox
  'wheel = zoom · drag = pan · double-click = fit': 'kolečko = přiblížení · tažení = posun · dvojklik = přizpůsobit', Fit: 'Přizpůsobit',
  'Click two points on the drawing (distance in mm)': 'Klikněte na dva body výkresu (vzdálenost v mm)',
  // outline wizard
  'Outline from picture': 'Obrys z obrázku', 'Detect:': 'Detekce:', '✚ Inside object': '✚ Uvnitř předmětu', '✖ Not this': '✖ Tohle ne',
  '▭ Box around object': '▭ Rámeček kolem předmětu', '◉ Object colour': '◉ Barva předmětu', '◌ Background colour': '◌ Barva pozadí', 'Clear hints': 'Smazat nápovědy',
  'Edit:': 'Úpravy:', '⬠ Polygon': '⬠ Mnohoúhelník', '◯ Lasso': '◯ Laso', '🖌 Brush': '🖌 Štětec', '＋ Add': '＋ Přidat', '− Remove': '− Odebrat', '✂ Cut out': '✂ Vyříznout',
  '↶ Undo': '↶ Zpět', Empty: 'Prázdný', Done: 'Hotovo', 'Detecting…': 'Hledám…', 'Candidates — most likely first': 'Kandidáti — nejpravděpodobnější první',
  '＋ / − on a candidate adds it to / cuts it from your edit — e.g. body ＋ wheels − shadow.': '＋ / − u kandidáta ho přidá k úpravě / vyřízne z ní — např. tělo ＋ kola − stín.',
  Detection: 'Detekce', Candidates: 'Kandidáti', Tolerance: 'Tolerance', Smoothing: 'Vyhlazení', 'Keep inner holes': 'Zachovat vnitřní díry', '↻ Detect again': '↻ Znovu detekovat',
  'Real size': 'Skutečná velikost', 'Width × height': 'Šířka × výška', 'mm — aspect ratio is kept (change it later in Dimensions).': 'mm — poměr stran se zachová (změníte později v Rozměrech).',
  'mm — the part keeps its scale, so what you do not change keeps its real size. Type a size to rescale.': 'mm — díl zachová měřítko, takže co neměníte, má stále skutečnou velikost. Zadáním velikosti přeškálujete.',
  'Use this outline': 'Použít tento obrys', 'Apply to the part': 'Použít na díl', 'Add as design layer': 'Přidat jako vrstvu designu', 'Apply to the layer': 'Použít na vrstvu',
  'Remove all detection hints': 'Odebrat všechny nápovědy detekce', 'Edit the selected outline by hand — or draw one from scratch': 'Upravit vybraný obrys ručně — nebo nakreslit nový',
  'Zoom: mouse wheel · pan: drag (no tool), middle mouse or Space + drag · keys + − 0': 'Přiblížení: kolečko · posun: tažení (bez nástroje), prostřední tlačítko nebo mezerník + tažení · klávesy + − 0',
  'Polygon (P): click corner points': 'Mnohoúhelník (P): klikejte na rohy', 'Lasso (L): drag a freehand loop': 'Laso (L): táhněte volnou smyčku', 'Brush (B): paint': 'Štětec (B): malujte',
  'Add (1)': 'Přidat (1)', 'Remove (2)': 'Odebrat (2)', 'Cut out (3): keep only what is inside the polygon / loop': 'Vyříznout (3): ponechat jen to, co je uvnitř mnohoúhelníku / smyčky',
  'Brush size (picture pixels)': 'Velikost štětce (pixely obrázku)', 'Start from an empty outline and draw it yourself': 'Začít s prázdným obrysem a nakreslit ho sami',
  'Leave edit mode (your edit stays as candidate ✎)': 'Ukončit úpravy (úprava zůstane jako kandidát ✎)', 'Colour tolerance (0 = automatic)': 'Tolerance barvy (0 = automaticky)',
  'Rounds off pixel steps and small bumps (pixels)': 'Zaoblí pixelové schody a malé hrbolky (pixely)', 'Thin cutting wall + flange, printed flange-down': 'Tenká řezná stěna + límec, tiskne se límcem dolů',
  'The whole shape, extruded': 'Celý tvar vytažený do výšky', 'Start with the plain outline and add your own objects': 'Začít s prostým obrysem a přidat vlastní objekty',
  'Continue editing': 'Pokračovat v úpravách', 'Discard your edit': 'Zahodit úpravu', 'Edit this outline by hand': 'Upravit tento obrys ručně', 'Add to your edit': 'Přidat k úpravě',
  'Cut from your edit': 'Vyříznout z úpravy', 'Click colours that belong to the object': 'Klikněte na barvy, které patří předmětu', 'Click colours of the background': 'Klikněte na barvy pozadí',
  'Click inside the object you want — only outlines containing the point are kept': 'Klikněte dovnitř požadovaného předmětu — zůstanou jen obrysy obsahující tento bod',
  'Click on something that is NOT the object (background, shadow, a neighbour) — outlines containing it are dropped': 'Klikněte na něco, co NENÍ předmět (pozadí, stín, soused) — obrysy, které to obsahují, se vyřadí',
  'Drag a box around the object — everything outside is treated as background': 'Táhněte rámeček kolem předmětu — vše mimo se bere jako pozadí',
  'Click two points to measure — in picture pixels and, with the size set, in mm': 'Klikněte na dva body pro měření — v pixelech obrázku a při zadané velikosti v mm',
  'Measure between two points (px / mm)': 'Měřit mezi dvěma body (px / mm)', '📏 Measure ': '📏 Měřit',
  'No outline found — give a hint (inside point, box, colours) or draw it with ✎ Edit outline.': 'Obrys nenalezen — dejte nápovědu (bod uvnitř, rámeček, barvy) nebo ho nakreslete přes ✎ Upravit obrys.',
  'No candidates.': 'Žádní kandidáti.', 'In use — your edit': 'Používaný — vaše úprava', 'Your edit': 'Vaše úprava', '● In use': '● Používaný', '(the part is made from it)': '(díl je z něj vyroben)',
  'Enter the real width / height in mm.': 'Zadejte skutečnou šířku / výšku v mm.', 'your edit — in use': 'vaše úprava — používaná', 'in use': 'používaný', 'your edit': 'vaše úprava',
  // 3D print
  'Export pieces STL (.zip)': 'Exportovat díly STL (.zip)', 'STEP (.zip)': 'STEP (.zip)', '← Back to whole model': '← Zpět na celý model', Printer: 'Tiskárna', '+ New printer': '+ Nová tiskárna',
  Edit: 'Upravit', 'Bed margin (mm)': 'Okraj podložky (mm)', 'Show build volume in 3D': 'Zobrazit tiskový prostor ve 3D', 'Fit check': 'Kontrola velikosti',
  'Joining split pieces': 'Spojování dílů', Joint: 'Spoj', 'Depth (mm)': 'Hloubka (mm)', 'Flare angle °': 'Úhel rozšíření °', 'Count per cut (0 = auto)': 'Počet na řez (0 = auto)',
  'Fit clearance (mm)': 'Vůle spoje (mm)', 'Knob size (mm)': 'Velikost výstupku (mm)', 'Alternate knob direction': 'Střídat směr výstupků', 'Length (mm)': 'Délka (mm)',
  'Height (mm)': 'Výška (mm)', 'Edge margin (mm)': 'Okraj (mm)', 'Screw holes': 'Otvory pro šrouby', 'Screw size (M…)': 'Velikost šroubu (M…)', 'Front skin (mm)': 'Přední stěna (mm)',
  Glue: 'Lepidlo', 'Glue channel (mm)': 'Kanálek pro lepidlo (mm)', 'Glue port Ø (mm)': 'Otvor pro lepidlo Ø (mm)', 'Channel + injection ports (back)': 'Kanálek + vstřikovací otvory (zezadu)',
  'Glue channel only': 'Jen kanálek pro lepidlo', 'No glue features': 'Bez prvků pro lepení',
  'Straight cut — glue the pieces (a glue channel and back-side injection ports keep glue off the front).': 'Rovný řez — díly se slepí (kanálek a vstřikovací otvory zezadu udrží lepidlo mimo přední stranu).',
  'Trapezoid tabs through the full thickness — the dovetail outline shows on the front. No extra parts.': 'Lichoběžníkové výstupky přes celou tloušťku — tvar rybinového spoje je vidět zepředu. Bez dalších dílů.',
  'Dovetails only behind a straight front skin: the front stays flat with a hairline seam. Pieces alternate male (print front-up) / female (print front-down); male pieces drop into the female sockets from the back.': 'Rybinové spoje jen za rovnou přední stěnou: přední strana zůstane rovná s vlasovou spárou. Díly se střídají samec (tisk lícem nahoru) / samice (tisk lícem dolů); samčí díly se zasunou do samičích zezadu.',
  'Round jigsaw knobs printed into the cut — press together. No extra parts.': 'Kulaté puzzle výstupky vytištěné v řezu — stačí zmáčknout. Bez dalších dílů.',
  'Bow-tie keys inlaid across each seam, printed separately and pressed in.': 'Motýlkové klíny vložené přes každou spáru, tištěné zvlášť a zamáčknuté.',
  'Rectangular pins in pockets inside the cut faces, printed separately.': 'Obdélníkové kolíky v kapsách uvnitř řezných ploch, tištěné zvlášť.',
  'A thin plate recessed across each seam (back by default), with optional screw pilot holes.': 'Tenká destička zapuštěná přes každou spáru (standardně zezadu), volitelně s otvory pro šrouby.',
  'The part is bent: curved parts usually need supports. You can also print it flat (hide the bends) and heat-bend it afterwards.': 'Díl je ohnutý: zakřivené díly obvykle potřebují podpory. Můžete ho také vytisknout rovný (skrýt ohyby) a ohnout teplem až potom.',
  'The back face has embossed design, so the part will not lie flat on the bed — print face-up with supports, or move the design to the front.': 'Zadní plocha má vytlačený design, díl tedy nebude ležet rovně na podložce — tiskněte lícem nahoru s podporami, nebo design přesuňte dopředu.',
  'Load a drawing to check printability.': 'Načtěte výkres pro kontrolu tisknutelnosti.', '✓ Fits on the build plate': '✓ Vejde se na tiskovou podložku',
  '✕ Does not fit in one piece': '✕ Nevejde se v jednom kuse', 'rotate 90° on plate': 'otočit o 90° na podložce', 'too big!': 'příliš velký!', 'back face up': 'zadní stranou nahoru',
  'Splitting…': 'Rozděluji…', 'Split anyway': 'Přesto rozdělit', 'Split to fit this printer': 'Rozdělit pro tuto tiskárnu',
  // AI chat
  'Checking for Claude Code…': 'Hledám Claude Code…', 'Claude Code connected': 'Claude Code připojen', 'Claude Code ready — send a message to start': 'Claude Code připraven — pošlete zprávu',
  'Claude Code not found': 'Claude Code nenalezen', 'The app server is not reachable': 'Server aplikace není dostupný', 'New chat': 'Nový chat', 'Start a new conversation': 'Začít novou konverzaci',
  'Claude stopped with an error.': 'Claude skončil s chybou.', 'Claude Code stopped': 'Claude Code se zastavil', 'Starting Claude Code…': 'Spouštím Claude Code…', Send: 'Odeslat', Stop: 'Zastavit',
  '📎 Photo': '📎 Fotka',
  '📎 Attach a photo (or paste / drop it here) — “Make a cookie cutter from this, 90 mm wide”.': '📎 Přiložte fotku (nebo ji vložte / přetáhněte sem) — „Udělej z toho vykrajovátko, 90 mm široké“.', 'Remove this photo': 'Odebrat tuto fotku',
  'Attach photos — or paste (Ctrl+V) or drop them here. Claude sees them and can trace one into a part.': 'Přiložit fotky — nebo je vložte (Ctrl+V) či přetáhněte sem. Claude je vidí a umí z nich obkreslit díl.',
  'Message Claude… (Enter = send, Shift+Enter = new line)': 'Zpráva pro Clauda… (Enter = odeslat, Shift+Enter = nový řádek)',
  "Undo the last change (Ctrl+Z) — the AI's changes are steps in the app's undo history": 'Vrátit poslední změnu (Ctrl+Z) — změny AI jsou kroky v historii aplikace',
  'Claude Code is not installed (or not found). Install it from claude.com/claude-code and sign in once; or set AUTO3D_CLAUDE to the path of claude.exe and restart the app.': 'Claude Code není nainstalovaný (nebo nebyl nalezen). Nainstalujte ho z claude.com/claude-code a jednou se přihlaste; nebo nastavte AUTO3D_CLAUDE na cestu ke claude.exe a aplikaci restartujte.',
  'reading the part': 'čte díl', 'looking at the 3D view': 'prohlíží 3D pohled', 'opening a file': 'otevírá soubor', 'opening the sample': 'otevírá ukázku',
  'tracing the picture': 'obkresluje obrázek', 'making the part from the outline': 'vyrábí díl z obrysu', 'setting dimensions': 'nastavuje rozměry',
  'choosing what to make': 'volí, co vyrobit', 'changing part options': 'mění volby dílu', 'adding a 3D object': 'přidává 3D objekt', 'adding a 2D shape': 'přidává 2D tvar',
  'adding a design layer': 'přidává vrstvu designu', 'changing an item': 'mění položku', 'removing an item': 'odebírá položku', 'adding a dimension': 'přidává kótu',
  'checking the printer fit': 'kontroluje tiskárnu', exporting: 'exportuje', undoing: 'vrací změnu',
  // checks / server messages (fixed texts)
  'No part outline found in the PDF (no thick vector lines). Scanned/raster drawings are not supported.': 'V PDF nebyl nalezen obrys dílu (žádné tlusté vektorové čáry). Skenované / rastrové výkresy nejsou podporovány.',
  'A drawing frame/border was detected and ignored.': 'Byl nalezen rámeček výkresu a ignorován.', 'No closed outline found in the drawing.': 'Ve výkresu nebyl nalezen uzavřený obrys.',
  'A closed shape inside a cutout was found; islands are not supported and it was ignored.': 'Uvnitř výřezu byl nalezen uzavřený tvar; ostrůvky nejsou podporovány a byl ignorován.',
  'More than one separate part outline found; only the largest one is modelled.': 'Nalezeno více samostatných obrysů; modeluje se jen největší.',
  'An arrowhead without a matching opposite arrow was found and ignored.': 'Nalezena šipka bez protější šipky — ignorována.',
  'The outline is empty after the 2D shapes were applied.': 'Po použití 2D tvarů je obrys prázdný.', 'The profile is empty after the 2D shapes were applied.': 'Po použití 2D tvarů je profil prázdný.',
  'Nothing to build: add at least one visible object that adds material (union).': 'Není co sestavit: přidejte alespoň jeden viditelný objekt, který přidává materiál (sjednocení).',
  'The objects cancel each other out — nothing is left.': 'Objekty se navzájem vyruší — nic nezbývá.', 'Scale must be greater than zero.': 'Měřítko musí být větší než nula.',
  // parts of a project (tabs in the top bar)
  'Close this part (it is removed from the project)': 'Zavřít tento díl (odebere se z projektu)',
  'The part on screen — double-click to rename': 'Díl na obrazovce — dvojklikem přejmenujete',
  'Click to show this part — double-click to rename': 'Kliknutím zobrazíte tento díl — dvojklikem přejmenujete',
  'Add a part to this project — every file you open becomes its own part': 'Přidat díl do projektu — každý otevřený soubor je samostatný díl',
  'The project file has no part in it.': 'Soubor projektu neobsahuje žádný díl.',
  'Nothing is left of the part.': 'Z dílu nic nezbylo.', 'height/depth must be greater than zero.': 'výška / hloubka musí být větší než nula.',
  'has no effect — it lies outside the face (check its mask, position and margin).': 'nemá žádný účinek — leží mimo plochu (zkontrolujte masku, polohu a okraj).',
  'Design layers apply to flat parts (drawings, outlines); on an imported 3D part use 3D objects instead (e.g. subtract a text object to engrave it).': 'Vrstvy designu platí pro ploché díly (výkresy, obrysy); u importovaného 3D dílu použijte 3D objekty (např. odečtěte textový objekt pro vyrytí).',
  'Front and back engravings overlap and together are as deep as the part — the overlap is cut through.': 'Přední a zadní rytina se překrývají a dohromady jsou hluboké jako díl — překryv je prořezán.',
  // dimension names from PDF drawings
  'Overall length': 'Celková délka', 'Overall height': 'Celková výška', 'Thickness (extrusion)': 'Tloušťka (vytažení)', 'Outer profile': 'Vnější profil',
  Width: 'Šířka', Height: 'Výška', Scale: 'Měřítko', 'Size X': 'Velikost X', 'Size Y': 'Velikost Y', 'Size Z': 'Velikost Z',
  'Click to edit · drag ↔ or scroll to change': 'Klikněte pro úpravu · táhněte ↔ nebo kolečkem změňte',
  '✕ or Delete (while pointing at it) removes it': '✕ nebo Delete (při najetí myší) ji odebere',
  'it is not dimensioned in the drawing': 've výkresu není okótována',
  'too big': 'příliš velký', '(too big!)': '(příliš velký!)', 'PDF drawing': 'výkres PDF', 'imported 3D file': 'importovaný 3D soubor',
  'outline (from a DXF drawing)': 'obrys (z výkresu DXF)', 'outline (traced from a picture)': 'obrys (obkreslený z obrázku)',
  'No dimension: the points coincide along that direction.': 'Žádná kóta: body v tomto směru splývají.',
  'Both picks lie at the same horizontal position.': 'Oba body leží ve stejné vodorovné poloze.', 'Both picks lie at the same vertical position.': 'Oba body leží ve stejné svislé poloze.',
  'New horizontal dimension': 'Nová vodorovná kóta', 'New vertical dimension': 'Nová svislá kóta', '↔ Horizontal': '↔ Vodorovně', '↕ Vertical': '↕ Svisle',
  'Drag a freehand loop': 'Táhněte volnou smyčku', 'Drag to paint': 'Táhněte a malujte', 'adds it to the outline': 'přidá to k obrysu',
  'removes it from the outline': 'odebere to z obrysu', 'keeps only what is inside it (cut the object out)': 'ponechá jen to, co je uvnitř (vyřízne předmět)',
  'Click corner points — double-click, Enter or a click on the first point closes it · Backspace / right-click removes the last point':
    'Klikejte na rohy — dvojklik, Enter nebo klik na první bod ho uzavře · Backspace / pravé tlačítko odebere poslední bod',
  'not this': 'tohle ne', 'cut out': 'vyříznout', 'not an image': 'není obrázek',
  'Wall thickness': 'Tloušťka stěny', 'Total height': 'Celková výška', 'Edge height': 'Výška hrany', 'Flange width': 'Šířka límce',
  'Flange thickness': 'Tloušťka límce', Clearance: 'Vůle', Thickness: 'Tloušťka', 'Grow / shrink': 'Zvětšit / zmenšit',
  'Butt joint (glue)': 'Tupý spoj (lepidlo)', 'Dovetail — through (interlocking, printed in)': 'Rybina — průchozí (zaklesnutí, tištěná v dílu)',
  'Dovetail — hidden, flat front (male / female)': 'Rybina — skrytá, rovná přední strana (samec / samice)', 'Jigsaw puzzle knobs (printed in)': 'Puzzle výstupky (tištěné v dílu)',
  'Butterfly keys (separate bow-tie parts)': 'Motýlkové klíny (samostatné díly)', 'Rectangular dowel pins (separate parts)': 'Obdélníkové kolíky (samostatné díly)',
  'Splice plate (separate recessed plate)': 'Spojovací destička (samostatná, zapuštěná)', 'Butterfly key': 'Motýlkový klín', 'Dowel pin': 'Kolík', 'Splice plate': 'Spojovací destička',
  'your colours': 'vaše barvy', 'GrabCut + your colours': 'GrabCut + vaše barvy', 'refined (GrabCut)': 'zpřesněno (GrabCut)',
  brightness: 'jas', saturation: 'sytost', edges: 'hrany',
  '2D shapes on the profile': '2D tvary na profilu', '2D shapes on the outline': '2D tvary na obrysu', '2D shapes on the footprint': '2D tvary na půdorysu',
  'Added to or cut from the profile itself before anything is built.': 'Přidávají se k samotnému profilu nebo se z něj vyřezávají ještě před sestavením.',
  'Added to or cut from the footprint itself before anything is built.': 'Přidávají se k samotnému půdorysu nebo se z něj vyřezávají ještě před sestavením.',
  'Added to or cut from the outline itself before anything is built — a cookie cutter wall follows them too.': 'Přidávají se k samotnému obrysu nebo se z něj vyřezávají ještě před sestavením — stěna vykrajovátka je také sleduje.',
  'The profile, grown or shrunk by an offset, extruded': 'Profil zvětšený nebo zmenšený o odsazení a vytažený',
  'The outline, grown or shrunk by an offset, extruded': 'Obrys zvětšený nebo zmenšený o odsazení a vytažený',
  'The footprint, grown or shrunk by an offset, extruded': 'Půdorys zvětšený nebo zmenšený o odsazení a vytažený',
  'A wall along the profile: the area between two offsets': 'Stěna podél profilu: oblast mezi dvěma odsazeními',
  'A wall along the outline: the area between two offsets': 'Stěna podél obrysu: oblast mezi dvěma odsazeními',
  'A wall along the footprint: the area between two offsets': 'Stěna podél půdorysu: oblast mezi dvěma odsazeními',
  // 3D model workspace
  '＋ New 3D model': '＋ Nový 3D model',
  '📂 Open ▾': '📂 Otevřít ▾', 'Open a drawing, a picture, a CAD / 3D file or a saved project — each file becomes its own part tab': 'Otevřít výkres, obrázek, CAD / 3D soubor nebo uložený projekt — každý soubor je samostatná záložka dílu',
  'PDF drawing…': 'Výkres PDF…', 'A dimensioned PDF drawing: its dimensions drive the part': 'Okótovaný výkres PDF: jeho kóty řídí díl',
  'Picture — trace an outline…': 'Obrázek — obkreslit obrys…', 'CAD / 3D file (DXF, DWG, STL, OBJ, STEP)…': 'CAD / 3D soubor (DXF, DWG, STL, OBJ, STEP)…',
  'Project…': 'Projekt…', 'A project saved with Save project (.a3d.json) — all its parts': 'Projekt uložený přes Uložit projekt (.a3d.json) — všechny jeho díly',
  'Save all parts of the project in one file (.a3d.json)': 'Uložit všechny díly projektu do jednoho souboru (.a3d.json)', 'Start a 3D model from scratch: sketch a rectangle or a circle, then extrude it': 'Začít 3D model od nuly: nakreslete obdélník nebo kruh a vysuňte ho',
  'Click to rename the project': 'Klikněte pro přejmenování projektu', '3D model': '3D model',
  Model: 'Model', 'steps, from the first to the last': 'kroky, od prvního k poslednímu', 'Make a part in 3 steps': 'Díl ve 3 krocích',
  'Building the 3D model…': 'Sestavuji 3D model…', Sketch: 'Skica', Extrude: 'Vysunutí',
  '▭ Rectangle': '▭ Obdélník', 'Draw a rectangle: click two corners (R)': 'Nakreslit obdélník: klikněte na dva rohy (R)',
  '◯ Circle': '◯ Kruh', 'Draw a circle: click the centre, then the edge (C)': 'Nakreslit kruh: klikněte na střed, pak na okraj (C)',
  '⬚ Select': '⬚ Vybrat', 'Select a shape to move it (drag), change its size or delete it (Esc)': 'Vyberte tvar pro posun (tažením), změnu velikosti nebo smazání (Esc)',
  '✓ Finish sketch': '✓ Dokončit skicu', 'Done drawing — next: Extrude (Enter)': 'Kreslení hotovo — dále: Vysunutí (Enter)',
  '✕ Cancel': '✕ Zrušit', 'Leave the sketch without changing the part': 'Opustit skicu bez změny dílu', 'Sketch on…': 'Skica na…',
  'click a flat face of the part — or a plane:': 'klikněte na rovnou plochu dílu — nebo na rovinu:', Right: 'Zprava',
  'Sketch on the Top plane (XY)': 'Skica na horní rovině (XY)', 'Sketch on the Front plane (XZ)': 'Skica na přední rovině (XZ)',
  'Sketch on the Right plane (YZ)': 'Skica na pravé rovině (YZ)', 'Do not start a sketch (Esc)': 'Nezačínat skicu (Esc)',
  '✏ Sketch': '✏ Skica', 'Start a sketch: on a plane, or on a flat face of the part (S)': 'Začít skicu: na rovině nebo na rovné ploše dílu (S)',
  '⬆ Extrude': '⬆ Vysunutí', 'Give a sketch a height: add material or cut (E)': 'Dát skice výšku: přidat materiál nebo řez (E)', 'Draw a sketch first': 'Nejprve nakreslete skicu',
  'Redo (Ctrl+Y)': 'Znovu (Ctrl+Y)', 'View from the front-right, above': 'Pohled zepředu zprava, shora', 'View from above': 'Pohled shora',
  'View from the front': 'Pohled zepředu', 'View from the right': 'Pohled zprava',
  'Change this step (or double-click it)': 'Změnit tento krok (nebo na něj dvakrát klikněte)', 'Delete this step': 'Smazat tento krok',
  'on Top': 'na horní rovině', 'on Front': 'na přední rovině', 'on Right': 'na pravé rovině', 'on a face': 'na ploše', 'cut through all': 'řez skrz vše',
  'Delete this shape (Delete)': 'Smazat tento tvar (Delete)', 'Delete shape': 'Smazat tvar', Tips: 'Tipy', 'Centre x': 'Střed x', 'Centre y': 'Střed y',
  'A shape inside another one becomes a hole. Click a size in the view to type it. Drag with the right mouse button to pan, wheel to zoom. Ctrl+Z undoes the last shape.':
    'Tvar uvnitř jiného tvaru je díra. Kliknutím na rozměr v pohledu ho napíšete. Pravým tlačítkem posunete pohled, kolečkem přiblížíte. Ctrl+Z vrátí poslední tvar.',
  'New sketch': 'Nová skica', 'Click a flat face of the part to sketch on it — holes, pockets and bosses go there. Or choose a plane in the bar above.':
    'Klikněte na rovnou plochu dílu a kreslete na ni — tam patří díry, kapsy a výstupky. Nebo zvolte rovinu v liště nahoře.',
  'New 3D model': 'Nový 3D model', 'Start with a sketch: draw a rectangle or a circle, then give it a height with Extrude.':
    'Začněte skicou: nakreslete obdélník nebo kruh a pak mu Vysunutím dejte výšku.', '✏ Start a sketch': '✏ Začít skicu',
  Size: 'Velikost', Volume: 'Objem', 'No solid yet — extrude a sketch.': 'Zatím žádné těleso — vysuňte skicu.', Next: 'Dále', Export: 'Export',
  'For 3D printing': 'Pro 3D tisk', 'For other CAD programs (exact circles and faces)': 'Pro jiné CAD programy (přesné kružnice a plochy)',
  'A sketch is not used yet — Extrude it.': 'Jedna skica zatím není použita — vysuňte ji.',
  'A sketch is not used yet (bright lines in the view) — Extrude it, or double-click its lines to change it.': 'Jedna skica zatím není použita (světlé čáry v pohledu) — vysuňte ji, nebo dvojklikem na její čáry ji změňte.',
  'Double-click to edit this sketch': 'Dvojklikem tuto skicu upravíte', 'Extrude a sketch to make the solid.': 'Vysuňte skicu a vznikne těleso.',
  'Click ✏ Sketch, then a flat face of the part, to add a hole, a pocket or a boss. Double-click a step to change it.':
    'Klikněte na ✏ Skica a pak na rovnou plochu dílu — přidáte díru, kapsu nebo výstupek. Dvojklikem na krok ho změníte.',
  'The 3D model workspace needs its CAD kernel.': 'Prostředí 3D modelu potřebuje své CAD jádro.',
  "Run this once in the app's folder, then restart the app:": 'Jednou spusťte ve složce aplikace a aplikaci restartujte:',
  'Cancelled — the model is shown as it was.': 'Zrušeno — model je zobrazen, jak byl.',
  'Sketching on the Top plane — click two corners to draw a rectangle.': 'Kreslíte na horní rovině — klikněte na dva rohy obdélníku.',
  'Pick a flat face — sketches go on flat faces.': 'Vyberte rovnou plochu — skici patří na rovné plochy.',
  'Draw a rectangle or a circle first — or Cancel.': 'Nejprve nakreslete obdélník nebo kruh — nebo zrušte.', 'Draw a sketch first (✏ Sketch).': 'Nejprve nakreslete skicu (✏ Skica).',
  'The distance must be greater than zero.': 'Vzdálenost musí být větší než nula.', 'A size must be greater than zero.': 'Rozměr musí být větší než nula.',
  'Click a flat face of the part to sketch on it — or choose Top / Front / Right above. Esc cancels.': 'Klikněte na rovnou plochu dílu a kreslete na ni — nebo nahoře zvolte Horní / Zepředu / Zprava. Esc zruší.',
  'Click the second corner (Esc = stop drawing).': 'Klikněte na druhý roh (Esc = přestat kreslit).', 'Click the first corner of a rectangle.': 'Klikněte na první roh obdélníku.',
  'Click to set the size (Esc = stop drawing).': 'Kliknutím nastavíte velikost (Esc = přestat kreslit).', 'Click the centre of a circle.': 'Klikněte na střed kruhu.',
  'Drag the shape to move it, click a size to type it, Delete removes it.': 'Tažením tvar posunete, kliknutím na rozměr ho napíšete, Delete ho smaže.',
  'Click a shape to select it — or pick ▭ Rectangle / ◯ Circle to draw.': 'Klikněte na tvar a vyberete ho — nebo zvolte ▭ Obdélník / ◯ Kruh a kreslete.',
  'Extrude — the preview is in the view. Enter = OK, Esc = Cancel.': 'Vysunutí — náhled je v pohledu. Enter = OK, Esc = Zrušit.',
  'Width — click to type': 'Šířka — klikněte a napište', 'Height — click to type': 'Výška — klikněte a napište', 'Diameter — click to type': 'Průměr — klikněte a napište',
  'Centre: distance from the sketch origin along x — click to type': 'Střed: vzdálenost od počátku skici ve směru x — klikněte a napište',
  'Centre: distance from the sketch origin along y — click to type': 'Střed: vzdálenost od počátku skici ve směru y — klikněte a napište',
  '⬆ Add material': '⬆ Přidat materiál', 'Add material': 'Přidat materiál', '⬇ Cut': '⬇ Řez', 'Remove material (holes, pockets)': 'Odebrat materiál (díry, kapsy)',
  'Through all': 'Skrz vše', 'Both sides (symmetric)': 'Na obě strany (symetricky)', '⇅ Flip direction': '⇅ Obrátit směr',
  'Extrude to the other side of the sketch': 'Vysunout na druhou stranu skici', OK: 'OK',
  'The preview is in the 3D view. Enter = OK, Esc = Cancel.': 'Náhled je ve 3D pohledu. Enter = OK, Esc = Zrušit.',
  'There is nothing to cut yet — make the first extrude “Add material”.': 'Zatím není z čeho řezat — první vysunutí musí být „Přidat materiál“.',
  'The sketch has no closed shape to use (draw a rectangle or a circle).': 'Skica nemá žádný uzavřený tvar (nakreslete obdélník nebo kruh).',
  'A rectangle needs a width and a height greater than zero.': 'Obdélník potřebuje šířku a výšku větší než nula.', 'A circle needs a diameter greater than zero.': 'Kruh potřebuje průměr větší než nula.',
  'Its sketch is missing or has a problem.': 'Jeho skica chybí nebo má problém.', 'The model has no solid yet — sketch a shape and extrude it.': 'Model zatím nemá těleso — nakreslete tvar a vysuňte ho.',
  'The solid operation failed.': 'Operace s tělesem selhala.', 'A sketch shape could not be turned into a face.': 'Z tvaru skici nešlo vytvořit plochu.',
  'The CAD kernel stopped unexpectedly while building — it restarts with the next change.': 'CAD jádro se při sestavování nečekaně zastavilo — při další změně se spustí znovu.',
  'The part on screen is a 3D model (sketches and extrudes) — the AI cannot edit 3D models yet. Ask the user to switch to another part tab, or open a drawing or a picture.':
    'The part on screen is a 3D model (sketches and extrudes) — the AI cannot edit 3D models yet. Ask the user to switch to another part tab, or open a drawing or a picture.',
  // sketcher: lines, locks
  '⟋ Line': '⟋ Čára', 'Draw lines: click point after point; click the first point to close the shape (L)': 'Kreslit čáry: klikejte bod po bodu; kliknutím na první bod tvar uzavřete (L)',
  'Select a shape or a corner to move it (drag) or delete it (Esc)': 'Vyberte tvar nebo roh a posuňte ho (tažením) nebo smažte (Esc)',
  'Click where the line starts.': 'Klikněte, kde čára začíná.',
  'Click the next point — click the first point to close the shape, double-click or Esc to stop.': 'Klikněte na další bod — kliknutím na první bod tvar uzavřete, dvojklik nebo Esc ukončí.',
  'Drag to move it · click a size to type it and lock it 🔒 · Delete removes it.': 'Tažením posunete · kliknutím na rozměr ho napíšete a zamknete 🔒 · Delete smaže.',
  'Click a shape or a corner to select it — or pick a drawing tool.': 'Klikněte na tvar nebo roh a vyberete ho — nebo zvolte nástroj kreslení.',
  'Locked — click to free this size': 'Zamčeno — kliknutím rozměr uvolníte', 'Free — click to lock this size as it is': 'Volné — kliknutím rozměr zamknete tak, jak je',
  'Length — click to type it (that locks it)': 'Délka — klikněte a napište (tím ji zamknete)', 'Diameter — click to type it (that locks it)': 'Průměr — klikněte a napište (tím ho zamknete)',
  'Distance from the origin along x — click to type it (that locks it)': 'Vzdálenost od počátku ve směru x — klikněte a napište (tím ji zamknete)',
  'Distance from the origin along y — click to type it (that locks it)': 'Vzdálenost od počátku ve směru y — klikněte a napište (tím ji zamknete)',
  '✓ Fully locked — every size is fixed.': '✓ Plně zamčeno — všechny rozměry jsou pevné.', Point: 'Bod',
  'Sizes and the position are shown in the view: click one to type it.': 'Rozměry a poloha jsou v pohledu: kliknutím na ně je napíšete.',
  'Delete it (Delete)': 'Smazat (Delete)',
  'A shape inside another one becomes a hole. Lines that meet at a point are joined; click the first point again to close a shape. 🔒 = locked size (it stays when other sizes change). Right mouse button pans, wheel zooms, Ctrl+Z undoes.':
    'Tvar uvnitř jiného tvaru je díra. Čáry, které se setkají v bodě, jsou spojené; opětovným kliknutím na první bod tvar uzavřete. 🔒 = zamčený rozměr (zůstane, když se jiné rozměry mění). Pravým tlačítkem posunete pohled, kolečkem přiblížíte, Ctrl+Z vrací.',
  'That does not fit the other locked sizes — unlock one of them first.': 'To nesedí s ostatními zamčenými rozměry — nejprve jeden z nich odemkněte.',
  'Draw a rectangle, lines or a circle first — or Cancel.': 'Nejprve nakreslete obdélník, čáry nebo kruh — nebo zrušte.',
  'A length must be greater than zero.': 'Délka musí být větší než nula.', 'A diameter must be greater than zero.': 'Průměr musí být větší než nula.',
  'A line ends at a point that does not exist.': 'Čára končí v bodě, který neexistuje.', 'A circle has no centre point.': 'Kruh nemá středový bod.',
  'Locked sketch sizes need the sketch solver: py -m pip install -r requirements-modeler.txt': 'Zamčené rozměry skici potřebují řešič skic: py -m pip install -r requirements-modeler.txt',
  // sketch dimensions
  '↔ Dimension': '↔ Kóta', 'Add a distance: click two points, circles, lines or edges of the part, then type the value (D)': 'Přidat vzdálenost: klikněte na dva body, kruhy, čáry nebo hrany dílu a napište hodnotu (D)',
  'Dimension: click a point, a circle (its centre), a line or an edge of the part — then a second one.': 'Kóta: klikněte na bod, kruh (jeho střed), čáru nebo hranu dílu — a pak na druhý.',
  'Now click the second one (Esc = start again).': 'Teď klikněte na druhý (Esc = začít znovu).', 'Which distance?': 'Jaká vzdálenost?',
  '↔ along x': '↔ ve směru x', '↕ along y': '↕ ve směru y', '⤢ straight': '⤢ přímá', 'Locked distance — click to type a new value': 'Zamčená vzdálenost — kliknutím napíšete novou hodnotu',
  'Locked sizes': 'Zamčené rozměry', 'Delete this lock': 'Smazat tento zámek',
  'Click a point, a circle, a line or an edge of the part.': 'Klikněte na bod, kruh, čáru nebo hranu dílu.',
  'Those two cannot be dimensioned — pick points, or a point and a straight horizontal / vertical edge.': 'Mezi těmito dvěma nelze kótovat — vyberte body, nebo bod a rovnou vodorovnou / svislou hranu.',
  'A distance must be greater than zero.': 'Vzdálenost musí být větší než nula.',
  'A shape inside another one becomes a hole. Lines that meet at a point are joined; click the first point again to close a shape. 🔒 = locked size (it stays when other sizes change). ↔ Dimension adds a distance between two points, circles or edges (also the part\'s edges, dashed). Right mouse button pans, wheel zooms, Ctrl+Z undoes.':
    'Tvar uvnitř jiného tvaru je díra. Čáry, které se setkají v bodě, jsou spojené; opětovným kliknutím na první bod tvar uzavřete. 🔒 = zamčený rozměr (zůstane, když se jiné rozměry mění). ↔ Kóta přidá vzdálenost mezi dvěma body, kruhy nebo hranami (i hranami dílu, čárkovaně). Pravým tlačítkem posunete pohled, kolečkem přiblížíte, Ctrl+Z vrací.',
  // fillet, chamfer, hole, steps on / off
  '◜ Fillet': '◜ Zaoblení', 'Round edges: click the edges, give the radius (F)': 'Zaoblit hrany: klikněte na hrany, zadejte poloměr (F)',
  '◸ Chamfer': '◸ Zkosení', 'Bevel edges: click the edges, give the size': 'Zkosit hrany: klikněte na hrany, zadejte velikost',
  '◎ Hole': '◎ Díra', 'Drill holes: click on a flat face where they go, give the diameter (H)': 'Vrtat díry: klikněte na rovnou plochu, kam patří, zadejte průměr (H)',
  Fillet: 'Zaoblení', Chamfer: 'Zkosení', 'Turn this step on again': 'Znovu zapnout tento krok', 'Turn this step off for now (it is kept)': 'Dočasně vypnout tento krok (zůstane zachován)', off: 'vypnuto',
  'Hole — click on a flat face where it goes (click again for more holes). Enter = OK, Esc = Cancel.': 'Díra — klikněte na rovnou plochu, kam patří (dalším kliknutím přidáte další). Enter = OK, Esc = Zrušit.',
  'Fillet — click the edges (or a face: all its edges). Enter = OK, Esc = Cancel.': 'Zaoblení — klikněte na hrany (nebo na plochu: všechny její hrany). Enter = OK, Esc = Zrušit.',
  'Chamfer — click the edges (or a face: all its edges). Enter = OK, Esc = Cancel.': 'Zkosení — klikněte na hrany (nebo na plochu: všechny její hrany). Enter = OK, Esc = Zrušit.',
  'Click the edges to round — click a face to take all of its edges, click a picked edge again to drop it.': 'Klikněte na hrany k zaoblení — kliknutím na plochu vezmete všechny její hrany, opětovným kliknutím na vybranou hranu ji vyřadíte.',
  'Click the edges to bevel — click a face to take all of its edges, click a picked edge again to drop it.': 'Klikněte na hrany ke zkosení — kliknutím na plochu vezmete všechny její hrany, opětovným kliknutím na vybranou hranu ji vyřadíte.',
  Radius: 'Poloměr', Diameter: 'Průměr', Depth: 'Hloubka', 'No edges picked yet': 'Zatím nejsou vybrány žádné hrany', 'Drop all edges': 'Vyřadit všechny hrany',
  "Click on a flat face where a hole goes — click again for more holes on the same face. A click near the face's centre snaps to it.": 'Klikněte na rovnou plochu, kam patří díra — dalším kliknutím přidáte další díry na stejnou plochu. Kliknutí poblíž středu plochy se k němu přichytí.',
  "Holes (from the face's centre)": 'Díry (od středu plochy)', 'Remove this hole': 'Odebrat tuto díru', 'No holes yet — click on a face.': 'Zatím žádné díry — klikněte na plochu.',
  'Click at least one edge first.': 'Nejprve klikněte alespoň na jednu hranu.', 'Click on a flat face where the hole goes.': 'Klikněte na rovnou plochu, kam patří díra.',
  'Holes go on flat faces — click a flat face.': 'Díry patří na rovné plochy — klikněte na rovnou plochu.',
  'The holes of one step go on one face — press OK, then make another Hole for the other face.': 'Díry jednoho kroku jsou na jedné ploše — stiskněte OK a pro druhou plochu udělejte další Díru.',
  'Click ✏ Sketch, then a flat face of the part, to add a pocket or a boss — or ◎ Hole, ◜ Fillet, ◸ Chamfer. Double-click a step to change it.':
    'Klikněte na ✏ Skica a pak na rovnou plochu dílu — přidáte kapsu nebo výstupek — nebo použijte ◎ Díra, ◜ Zaoblení, ◸ Zkosení. Dvojklikem na krok ho změníte.',
  'There is no solid yet to round.': 'Zatím není těleso k zaoblení.', 'There is no solid yet to drill into.': 'Zatím není těleso k vrtání.',
  'Click on a face where the hole goes.': 'Klikněte na plochu, kam patří díra.', 'Pick at least one edge.': 'Vyberte alespoň jednu hranu.',
  'The size must be greater than zero.': 'Velikost musí být větší než nula.',
  'This rounding does not fit (too big for the edges or faces next to it) — try a smaller size.': 'Toto zaoblení se nevejde (je moc velké pro sousední hrany nebo plochy) — zkuste menší velikost.',
  'This bevel does not fit (too big for the edges or faces next to it) — try a smaller size.': 'Toto zkosení se nevejde (je moc velké pro sousední hrany nebo plochy) — zkuste menší velikost.',
  'An edge it uses is no longer there — change this step and pick the edges again.': 'Hrana, kterou krok používá, už neexistuje — upravte krok a vyberte hrany znovu.',
  'The radius must be greater than zero.': 'Poloměr musí být větší než nula.', 'The diameter must be greater than zero.': 'Průměr musí být větší než nula.',
  'The depth must be greater than zero.': 'Hloubka musí být větší než nula.',
  // revolve, shell
  on: 'na', 'Sketch on the Top plane': 'Skica na horní rovině', 'Sketch on the Front plane': 'Skica na přední rovině', 'Sketch on the Right plane': 'Skica na pravé rovině',
  '⟳ Revolve': '⟳ Rotace', 'Spin a sketch around an axis (vases, knobs, wheels)': 'Otočit skicu kolem osy (vázy, knoflíky, kola)', Revolve: 'Rotace',
  '▢ Shell': '▢ Skořepina', 'Hollow the part out: click the face(s) to leave open, give the wall thickness': 'Vydutit díl: klikněte na plochy, které zůstanou otevřené, zadejte tloušťku stěny', Shell: 'Skořepina',
  Axis: 'Osa', Angle: 'Úhel', Wall: 'Stěna', "The sketch's vertical axis": 'Svislá osa skici', "The sketch's horizontal axis": 'Vodorovná osa skici',
  'The sketch is spun around the axis — draw half of the shape on one side of it (e.g. half a vase beside the vertical axis).': 'Skica se otočí kolem osy — nakreslete polovinu tvaru na jednu stranu od ní (např. polovinu vázy vedle svislé osy).',
  'Click the face(s) to leave open — e.g. the top of a cup or a box. Click a picked face in the list to drop it.': 'Klikněte na plochy, které zůstanou otevřené — např. horní stranu hrnku nebo krabičky. Vybranou plochu vyřadíte v seznamu.',
  'No face picked yet — click the face to leave open.': 'Zatím není vybrána plocha — klikněte na plochu, která zůstane otevřená.', 'Close this face again': 'Tuto plochu opět uzavřít',
  'Click the face(s) to leave open first.': 'Nejprve klikněte na plochy, které zůstanou otevřené.',
  'Revolve — choose the axis and the angle; the preview is in the view. Enter = OK, Esc = Cancel.': 'Rotace — zvolte osu a úhel; náhled je v pohledu. Enter = OK, Esc = Zrušit.',
  'Shell — click the face(s) to leave open, give the wall thickness. Enter = OK, Esc = Cancel.': 'Skořepina — klikněte na plochy, které zůstanou otevřené, zadejte tloušťku stěny. Enter = OK, Esc = Zrušit.',
  'There is no solid yet to hollow out.': 'Zatím není těleso k vydutí.', 'The shape could not be revolved.': 'Tvar nešlo otočit.',
  'The shape crosses the axis — for a revolve it must lie on one side of the axis.': 'Tvar protíná osu — pro rotaci musí ležet na jedné straně osy.',
  'The axis line is no longer in the sketch — choose the axis again.': 'Čára osy už ve skice není — zvolte osu znovu.', 'The axis line has no length.': 'Čára osy nemá délku.',
  'A face it uses is no longer there — change this step and pick the faces again.': 'Plocha, kterou krok používá, už neexistuje — upravte krok a vyberte plochy znovu.',
  'The wall thickness must be greater than zero.': 'Tloušťka stěny musí být větší než nula.', 'Click the face(s) to leave open (e.g. the top of a cup).': 'Klikněte na plochy, které zůstanou otevřené (např. horní stranu hrnku).',
  'The wall is too thick for this part — at most half its smallest size.': 'Stěna je pro tento díl moc tlustá — nejvýše polovina jeho nejmenšího rozměru.',
  'The walls could not be made this thick here — try a thinner wall.': 'Stěny tu nejdou udělat tak tlusté — zkuste tenčí stěnu.', 'The angle must be greater than zero.': 'Úhel musí být větší než nula.',
  // outlines in 3D models, printing copies
  '◆ To 3D model': '◆ Do 3D modelu', "Make a 3D model from this part's outline: a new model tab with the outline as its first sketch (then extrude it, add holes, roundings…)":
    'Udělat 3D model z obrysu tohoto dílu: nová záložka modelu s obrysem jako první skicou (pak ho vysuňte, přidejte díry, zaoblení…)',
  '🖼 Outline': '🖼 Obrys', 'Insert an outline from a picture, a DXF / DWG drawing or a PDF drawing (as one shape you can move and size)': 'Vložit obrys z obrázku, výkresu DXF / DWG nebo PDF (jako jeden tvar, který lze posouvat a měnit jeho velikost)',
  Outline: 'Obrys', 'Corner x': 'Roh x', 'Corner y': 'Roh y', 'Width of the outline — click to type it (the height follows)': 'Šířka obrysu — klikněte a napište (výška se přizpůsobí)',
  "Drag it in the view to move it. The corner is its lower-left corner, from the sketch's origin.": 'Tažením v pohledu ho posunete. Roh je jeho levý dolní roh, měřený od počátku skici.',
  '3D print': '3D tisk', 'Check it fits your printer, split it into pieces with joints — in a printing copy of this part.': 'Zkontrolujte, že se vejde na tiskárnu, rozdělte ho na díly se spoji — v tiskové kopii tohoto dílu.',
  '🖨 Prepare for 3D print': '🖨 Připravit pro 3D tisk',
  'A 3D model was made from the outline — give it a height (Extrude), then add holes, roundings…': 'Z obrysu vznikl 3D model — dejte mu výšku (Vysunutí) a pak přidejte díry, zaoblení…',
  'This part has no outline to use.': 'Tento díl nemá obrys k použití.', 'The drawing has errors — fix them in Checks first.': 'Výkres má chyby — nejprve je opravte v Kontrolách.',
  'Hidden (still used)': 'Skryté (stále platí)', Show: 'Zobrazit', Hide: 'Skrýt', 'Show this dimension in the view again': 'Znovu zobrazit tuto kótu v pohledu',
  'Hide this dimension from the view (the drawing still sets it)': 'Skrýt tuto kótu z pohledu (výkres ji stále určuje)', 'Hide this dimension (the drawing still sets it)': 'Skrýt tuto kótu (výkres ji stále určuje)',
  '✕ or Delete (while pointing at it) hides it': '✕ nebo Delete (při najetí myší) ji skryje',
  'Hide this size (and unlock it) — ↔ Dimension on the shape shows it again': 'Skrýt tento rozměr (a odemknout) — ↔ Kóta na tvaru ho znovu zobrazí',
  'Measured distance (free) — click to type a value and lock it': 'Měřená vzdálenost (volná) — klikněte, napište hodnotu a zamkněte ji',
  'Free — it only measures. Click to lock it at this value': 'Volná — jen měří. Kliknutím ji zamknete na této hodnotě',
  'Locked — click to free it (it then only measures)': 'Zamčená — kliknutím ji uvolníte (pak jen měří)', 'Lock it at this value': 'Zamknout na této hodnotě',
  'Free it (it then only measures)': 'Uvolnit (pak jen měří)', 'Delete this dimension': 'Smazat tuto kótu', Dimensions: 'Rozměry',
  'Now click the second one — the same line or circle again for its own size (Esc = start again).': 'Teď klikněte na druhý — na stejnou čáru nebo kruh znovu pro jeho vlastní rozměr (Esc = začít znovu).',
  'circle (its centre)': 'kruh (jeho střed)', origin: 'počátek', 'corner of the part': 'roh dílu', point: 'bod', line: 'čára', 'edge of the part': 'hrana dílu',
  'looking at the parts': 'prohlíží díly', 'opening a part': 'otevírá díl', 'starting a 3D model': 'zakládá 3D model', 'reading the 3D model': 'čte 3D model',
  'finding faces and edges': 'hledá plochy a hrany', 'adding a step': 'přidává krok', 'changing a step': 'mění krok', 'deleting a step': 'maže krok',
  'turning a step off / on': 'vypíná / zapíná krok', 'preparing the print': 'připravuje tisk', 'reading a guide': 'čte návod',
  // measure, section, mass
  '📏 Measure': '📏 Měřit', 'Measure: click a face or an edge (its size), or two spots (the distance between them) (M)': 'Měření: klikněte na plochu nebo hranu (její velikost), nebo na dvě místa (vzdálenost mezi nimi) (M)',
  '✂ Section': '✂ Řez', 'Look inside: cut the view along X, Y or Z': 'Pohled dovnitř: řez pohledem podél X, Y nebo Z',
  'Measure — click a face or an edge for its size, or two spots for the distance between them. Esc ends.': 'Měření — klikněte na plochu nebo hranu pro její velikost, nebo na dvě místa pro vzdálenost mezi nimi. Esc ukončí.',
  'Circular edge': 'Kruhová hrana', 'Round face': 'Válcová plocha', 'Flat face': 'Rovná plocha', Length: 'Délka', Corner: 'Roh', Point: 'Bod',
  'Click a second spot for the distance.': 'Klikněte na druhé místo pro vzdálenost.', 'Click again to measure from a new spot.': 'Dalším kliknutím měříte od nového místa.',
  'Show the other side': 'Zobrazit druhou stranu', 'No section': 'Bez řezu', Mass: 'Hmotnost', '(solid)': '(plný)', Material: 'Materiál',
  'setting the material': 'nastavuje materiál',
  // assemblies
  Assembly: 'Sestava', '＋ New assembly': '＋ Nová sestava', 'its parts': 'její díly', 'Put parts together': 'Sestavení dílů',
  '＋ Insert part ▾': '＋ Vložit díl ▾', 'Add a 3D model part of this project': 'Přidat 3D model z tohoto projektu', 'Make a 3D model part first (＋ New 3D model)': 'Nejprve udělejte 3D model (＋ Nový 3D model)',
  'No 3D model parts yet': 'Zatím žádné 3D modely', '🧲 Snap face to face': '🧲 Přichytit plochou k ploše', 'Click a face of the part to move, then the face it goes onto (S)': 'Klikněte na plochu dílu, který se má posunout, pak na plochu, na kterou patří (S)',
  Explode: 'Rozložit', 'Pull the parts apart to see them (the placement does not change)': 'Oddálit díly od sebe, aby byly vidět (umístění se nemění)',
  'One more of this part': 'Ještě jeden tento díl', 'Take it out of the assembly': 'Vyjmout ze sestavy', '⟲ 90° X': '⟲ 90° X', '⟲ 90° Y': '⟲ 90° Y', '⟲ 90° Z': '⟲ 90° Z',
  '🧲 Snap it onto another face': '🧲 Přichytit na jinou plochu', 'Back to its place in its own model': 'Zpět na místo ve vlastním modelu', 'Reset its place': 'Vrátit umístění', 'Take it out': 'Vyjmout',
  'Parts list': 'Kusovník', Qty: 'Ks', Total: 'Celkem', 'All parts in one STL, as placed': 'Všechny díly v jednom STL, jak jsou umístěny',
  'All parts as separate bodies in one STEP file': 'Všechny díly jako samostatná tělesa v jednom souboru STEP',
  "To print, open each part's tab and use 🖨 Prepare for 3D print there.": 'Pro tisk otevřete záložku každého dílu a použijte tam 🖨 Připravit pro 3D tisk.',
  'Insert 3D model parts of this project with ＋ Insert part, then snap them together face to face.': 'Vložte 3D modely tohoto projektu přes ＋ Vložit díl a pak je přichyťte plochou k ploše.',
  '🧲 Click a face of the part to move (Esc cancels).': '🧲 Klikněte na plochu dílu, který se má posunout (Esc zruší).',
  '🧲 Now click the face it goes onto (on another part).': '🧲 Teď klikněte na plochu, na kterou patří (na jiném dílu).',
  '🧲 Click the face of this part that goes onto another one.': '🧲 Klikněte na plochu tohoto dílu, která se přiloží k jinému.',
  'Snap works on flat faces — click flat faces.': 'Přichycení funguje na rovných plochách — klikněte na rovné plochy.', 'Click a flat face.': 'Klikněte na rovnou plochu.',
  'First a face of the selected part.': 'Nejprve plochu vybraného dílu.', 'Click a face of another part.': 'Klikněte na plochu jiného dílu.',
  'Snapped — nudge it in the panel if needed.': 'Přichyceno — případně ho dolaďte v panelu.', 'This part has no solid yet.': 'Tento díl zatím nemá těleso.',
  'This part is no longer in the project.': 'Tento díl už v projektu není.', 'The assembly is empty — insert parts first.': 'Sestava je prázdná — nejprve vložte díly.',
  'starting an assembly': 'zakládá sestavu', 'reading the assembly': 'čte sestavu', 'inserting a part': 'vkládá díl', 'snapping parts together': 'přichycuje díly',
  'placing a part': 'umisťuje díl', 'finding where fasteners fit': 'hledá místa pro spojovací prvky', 'adding fasteners': 'přidává spojovací prvky', 'taking a part out': 'vyjímá díl',
  '⁂ Pattern': '⁂ Pole', 'Pattern': 'Pole', '▦ In a row': '▦ V řadě', '◌ Around': '◌ Dokola', 'Repeat': 'Opakovat', 'How many': 'Kolik',
  'The copies changed nothing — they may land outside the part or on top of each other. Check the direction and the spacing.': 'Kopie nic nezměnily – možná leží mimo díl nebo na sobě. Zkontrolujte směr a rozestup.',
  'Apart': 'Rozestup', 'Direction': 'Směr', 'Around': 'Kolem', 'The other way': 'Opačným směrem',
  'Repeat a step (holes, a boss, a cut) in a row or around a circle: give how many and how far apart': 'Opakovat krok (díry, výstupek, výřez) v řadě nebo dokola: zadejte kolik a jak daleko od sebe',
  'Evenly around the axis through the origin. Or click a round face (a hole, a shaft) to go around its axis.': 'Rovnoměrně kolem osy přes počátek. Nebo klikněte na válcovou plochu (díru, hřídel) – pak kolem její osy.',
  'Evenly around the axis of the round face you clicked.': 'Rovnoměrně kolem osy válcové plochy, na kterou jste klikli.',
  'Or click a straight edge in the view to go along it.': 'Nebo klikněte na rovnou hranu v pohledu – pole půjde podél ní.',
  'Along the edge you clicked.': 'Podél hrany, na kterou jste klikli.',
  'Make something to repeat first — a hole, a boss or a cut.': 'Nejdřív vytvořte, co se má opakovat – díru, výstupek nebo výřez.',
  'Click a round face — the pattern goes around its axis.': 'Klikněte na válcovou plochu – pole půjde kolem její osy.',
  'Pattern — how many and how far apart. Click an edge for the direction (or a round face for the axis). Enter = OK, Esc = Cancel.': 'Pole – kolik a jak daleko od sebe. Klikněte na hranu pro směr (nebo na válcovou plochu pro osu). Enter = OK, Esc = Zrušit.',
  '◠ Arc': '◠ Oblouk', Arc: 'Oblouk', 'arc (its centre)': 'oblouk (jeho střed)',
  'Draw an arc: click where it starts and ends, then bend it with the mouse and click (A)': 'Nakreslit oblouk: klikněte na začátek a konec, pak ho myší ohněte a klikněte (A)',
  'Click where the arc starts.': 'Klikněte, kde oblouk začíná.', 'Click where the arc ends.': 'Klikněte, kde oblouk končí.',
  'Move the mouse to bend the arc, click to place it (Esc = stop drawing).': 'Pohybem myši oblouk ohněte, kliknutím ho umístěte (Esc = konec kreslení).',
  'Move the mouse to one side to bend the arc.': 'Posuňte myš stranou, aby se oblouk ohnul.',
  'Open the AI chat — Claude works on the part or assembly on screen': 'Otevřít AI chat – Claude pracuje s dílem nebo sestavou na obrazovce',
  'Close the chat (it keeps the conversation)': 'Zavřít chat (konverzace zůstane)',
  'Each hole keeps its distance from the edge it is measured from, also when the part changes. ⇄ measures from the other side.': 'Každá díra drží vzdálenost od hrany, od které je kótovaná, i když se díl změní. ⇄ kótuje od druhé strany.',
  'mm from the left edge': 'mm od levé hrany', 'mm from the right edge': 'mm od pravé hrany', 'mm from the lower edge': 'mm od spodní hrany', 'mm from the upper edge': 'mm od horní hrany',
  "from the face's centre": 'od středu plochy', 'Measure from the edge on the other side': 'Kótovat od hrany na druhé straně',
  'There is no edge on the other side to measure from.': 'Na druhé straně není hrana, od které kótovat.', Holes: 'Díry',
  "A dimension's edge of the part is gone — its distance is kept from where the edge was.": 'Hrana dílu, od které vede kóta, zmizela – vzdálenost zůstává od místa, kde hrana byla.',
  "The sketch's sizes no longer fit the part's new shape — open the sketch and unlock one.": 'Rozměry skici už nesedí na nový tvar dílu – otevřete skicu a jeden odemkněte.',
  '◜ Round corner': '◜ Zaoblit roh', 'Round a corner of lines: click the corner, type the radius (F)': 'Zaoblit roh čar: klikněte na roh, zadejte poloměr (F)',
  'Round corner: click a corner where two lines meet, then type the radius.': 'Zaoblení rohu: klikněte na roh, kde se setkávají dvě čáry, a zadejte poloměr.',
  'Click a corner where two lines meet.': 'Klikněte na roh, kde se setkávají dvě čáry.', 'Round a corner where exactly two lines meet.': 'Zaoblit lze roh, kde se setkávají právě dvě čáry.',
  'That radius is too big for these lines.': 'Tento poloměr je na tyto čáry příliš velký.', 'corner': 'roh',
  Distance: 'Vzdálenost', 'Up to a face': 'K ploše', 'A height you type': 'Výška, kterou zadáte',
  'As far as a face of the part — it follows the face when the part changes': 'Až k ploše dílu — sleduje ji, když se díl změní',
  'Click a flat face of the part (parallel to the sketch).': 'Klikněte na rovnou plochu dílu (rovnoběžnou se skicou).', Offset: 'Odsazení',
  'Offset: more = past the face, less (negative) = short of it. Click another face to change it.': 'Odsazení: víc = za plochu, méně (záporné) = před ni. Kliknutím na jinou plochu ji změníte.',
  'Up to a face — click a flat face of the part. Enter = OK, Esc = Cancel.': 'K ploše — klikněte na rovnou plochu dílu. Enter = OK, Esc = Zrušit.',
  'Click the face to go up to first.': 'Nejdřív klikněte na plochu, ke které se má vysunout.', 'Click a flat face of the part.': 'Klikněte na rovnou plochu dílu.',
  'Measure from another edge or hole: click it in the view': 'Kótovat od jiné hrany nebo díry: klikněte na ni v pohledu',
  'mm right of the hole': 'mm vpravo od díry', 'mm left of the hole': 'mm vlevo od díry', 'mm above the hole': 'mm nad dírou', 'mm below the hole': 'mm pod dírou',
  'Click a straight edge running up / down on this face, or another hole.': 'Klikněte na rovnou svislou hranu této plochy nebo na jinou díru.',
  'Click a straight edge running left / right on this face, or another hole.': 'Klikněte na rovnou vodorovnou hranu této plochy nebo na jinou díru.',
  'Hole — click on a flat face where it goes (click again for more holes). Enter = OK, Esc = Cancel.': 'Díra — klikněte na rovnou plochu, kam patří (dalším kliknutím přidáte další díry). Enter = OK, Esc = Zrušit.',
  'Add a part of this project: a 3D model ◆, a quick part ▤ (drawing, picture, import) or another assembly ◇ (as one unit)': 'Přidat díl projektu: 3D model ◆, rychlý díl ▤ (výkres, obrázek, import) nebo jinou sestavu ◇ (jako celek)',
  'This assembly has no parts with a solid yet.': 'Tato sestava zatím nemá díly s tělesem.',
  'Make a part first (＋ New 3D model, or open a drawing / picture)': 'Nejdřív vytvořte díl (＋ Nový 3D model, nebo otevřete výkres / obrázek)', 'No parts yet': 'Zatím žádné díly',
  'Insert parts of this project (3D models and quick parts) with ＋ Insert part, then snap them together face to face.': 'Vložte díly projektu (3D modely i rychlé díly) přes ＋ Vložit díl a pak je přichyťte plochou k ploše.',
  'The quick part could not be made solid.': 'Z rychlého dílu se nepodařilo udělat těleso.', "The solid's data is damaged.": 'Data tělesa jsou poškozená.',
  'Move the sketch plane along its normal (e.g. 30 mm above the bed — for a loft\'s second profile)': 'Posunout rovinu skici podél její normály (např. 30 mm nad podložku — pro druhý profil šablonování)',
  '⧫ Loft': '⧫ Šablonování', Loft: 'Šablonování', '〰 Sweep': '〰 Tažení', Sweep: 'Tažení', Solid: 'Těleso', From: 'Od', To: 'Do', Profile: 'Profil', Path: 'Dráha',
  'A shape from one outline to another (e.g. a square base to a round top): two sketches, one above the other': 'Tvar z jednoho obrysu do druhého (např. ze čtvercové základny do kulatého vršku): dvě skici nad sebou',
  'Move an outline along a path (pipes, handles, rails): a profile sketch and a path sketch': 'Posunout obrys po dráze (trubky, madla, lišty): skica profilu a skica dráhy',
  'Loft — choose the sketch it starts from and the one it goes to. Enter = OK, Esc = Cancel.': 'Šablonování — vyberte skicu, ze které začíná, a skicu, do které vede. Enter = OK, Esc = Zrušit.',
  'Sweep — choose the outline (profile) and the path it moves along. Enter = OK, Esc = Cancel.': 'Tažení — vyberte obrys (profil) a dráhu, po které se posune. Enter = OK, Esc = Zrušit.',
  "Each sketch: one closed outline. Put them one above the other (a sketch's Offset moves its plane up).": 'Každá skica: jeden uzavřený obrys. Dejte je nad sebe (Odsazení skici posune její rovinu nahoru).',
  "The profile: a closed outline at the start of the path, across it. The path: lines and arcs joined end to end.": 'Profil: uzavřený obrys na začátku dráhy, napříč k ní. Dráha: čáry a oblouky navazující na sebe.',
  'Draw two sketches first.': 'Nejdřív nakreslete dvě skici.',
  'Tangent arc: it continues the line — click where it ends (Shift-click: a free arc; Esc = stop drawing).': 'Tečný oblouk: navazuje na čáru — klikněte, kde končí (Shift+klik: volný oblouk; Esc = konec kreslení).',
  'Click where the arc starts (at the end of a line: it continues the line smoothly).': 'Klikněte, kde oblouk začíná (na konci čáry: plynule na ni naváže).',
  "Click beside the line's direction to bend the arc.": 'Klikněte stranou od směru čáry, aby se oblouk ohnul.',
  '✂ Trim': '✂ Oříznout', 'Cut away a piece of a line, circle or arc — up to where other shapes cross it (T)': 'Odříznout kus čáry, kružnice nebo oblouku — až k místu, kde ho kříží jiný tvar (T)',
  'Trim: click the piece of a line, circle or arc to cut away — up to where other shapes cross it.': 'Oříznout: klikněte na kus čáry, kružnice nebo oblouku, který má zmizet — až k místům, kde ho kříží jiné tvary.',
  'Click a line, circle or arc to trim.': 'Klikněte na čáru, kružnici nebo oblouk, který chcete oříznout.', 'cut away': 'odříznout',
  '⧈ Offset': '⧈ Odsadit', 'A parallel copy of a closed shape, a distance outside or inside it (O)': 'Rovnoběžná kopie uzavřeného tvaru ve vzdálenosti vně nebo uvnitř (O)',
  'Offset: click a closed shape — a circle, an outline of lines / arcs, or a picture outline — then type the distance (negative = inside).': 'Odsadit: klikněte na uzavřený tvar — kružnici, obrys z čar / oblouků nebo obrys z obrázku — a zadejte vzdálenost (záporná = dovnitř).',
  'Offset by': 'Odsadit o', 'Negative = inside.': 'Záporně = dovnitř.', 'Type a distance (not 0).': 'Zadejte vzdálenost (ne 0).',
  'Click a closed shape: a circle, an outline of lines / arcs joined all round, or a picture outline.': 'Klikněte na uzavřený tvar: kružnici, obrys z čar / oblouků spojených dokola nebo obrys z obrázku.',
  'That distance is bigger than a rounding of the outline.': 'Vzdálenost je větší než zaoblení obrysu.', 'That distance is bigger than the circle.': 'Vzdálenost je větší než kružnice.',
  'This outline has a sharp corner next to an arc — round it (◜) or offset its pieces one by one.': 'Obrys má ostrý roh vedle oblouku — zaoblete ho (◜) nebo odsaďte jeho části jednotlivě.',
  'Nothing is left — the outline is thinner than that.': 'Nic nezbude — obrys je tenčí.', 'Give an outline and a distance.': 'Zadejte obrys a vzdálenost.',
  'Aa Text / picture': 'Aa Text / obrázek', 'Decorate a flat face: text or a picture outline, raised or engraved': 'Ozdobit rovnou plochu: text nebo obrys obrázku, vystouplý nebo vyrytý',
  Decoration: 'Ozdoba', 'Aa Text': 'Aa Text', '🖼 Picture': '🖼 Obrázek', Text: 'Text', Raised: 'Vystouplé', Engraved: 'Vyryté',
  'Choose a picture…': 'Vybrat obrázek…', 'Another picture…': 'Jiný obrázek…', 'Type some text, or choose a picture.': 'Napište text nebo vyberte obrázek.',
  'Click on a flat face where it goes.': 'Klikněte na rovnou plochu, kam patří.', 'Click on a flat face of the part where it goes.': 'Klikněte na rovnou plochu dílu, kam patří.',
  "Click on the face again to move it — near the face's centre it snaps to it.": 'Dalším kliknutím na plochu ho posunete — u středu plochy se k němu přichytí.',
  'Text / picture — click on a flat face where it goes (click again to move it). Enter = OK, Esc = Cancel.': 'Text / obrázek — klikněte na rovnou plochu, kam patří (dalším kliknutím ho posunete). Enter = OK, Esc = Zrušit.',
  'There is no solid yet to decorate.': 'Zatím není co zdobit.',
  'Snapped — it now follows that part (moving it by hand unlinks it).': 'Přichyceno — teď ten díl následuje (posunutí rukou vazbu zruší).',
  'Snapped — not linked (the other part already follows this one).': 'Přichyceno — bez vazby (druhý díl už následuje tento).',
  'Moved by hand — it no longer follows the part it was snapped to.': 'Posunuto rukou — už nenásleduje díl, ke kterému byl přichycen.',
  '⚠ Its face is gone — snap it again.': '⚠ Jeho plocha zmizela — přichyťte ho znovu.', Unlink: 'Zrušit vazbu',
  'Keep it where it is, but no longer follow': 'Nechat ho na místě, ale už nenásledovat',
  '📐 Drawing (PDF)': '📐 Výkres (PDF)', 'A 2D drawing: front, top and right views, sizes, holes, title block': '2D výkres: pohled zepředu, shora a zprava, rozměry, díry, rohové razítko',
  'PDF — 2D drawing (views, sizes)': 'PDF — 2D výkres (pohledy, rozměry)', 'Exported the drawing (PDF).': 'Výkres exportován (PDF).',
  '✏ Sketch on this face': '✏ Skica na této ploše', '◎ Hole here': '◎ Díra sem', 'Aa Text / picture here': 'Aa Text / obrázek sem',
  '◜ Round its edges': '◜ Zaoblit její hrany', '◸ Bevel its edges': '◸ Zkosit její hrany', '▢ Hollow out, open here': '▢ Vydutit, otevřít zde',
  '● Turn it on': '● Zapnout', '◌ Turn it off': '◌ Vypnout',
  'Click to change it': 'Kliknutím změníte', 'That size does not fit here.': 'Tato velikost sem nepasuje.', Size: 'Velikost', Wall: 'Stěna',
  "That does not fit the sketch's other locked sizes — open the sketch and unlock one.": 'To nesedí na ostatní zamčené rozměry skici — otevřete skicu a jeden odemkněte.',
  '🔗 Joint ▾': '🔗 Vazba ▾', Touch: 'Dotyk', Gap: 'Mezera', Flush: 'Zarovnat', 'Pin in hole': 'Čep do díry', Parallel: 'Rovnoběžně',
  'Hold a part against another one: choose how, then click a face of the part to move and the face it goes to (S = touch)': 'Přidržet díl u jiného: vyberte jak, pak klikněte na plochu dílu, který se posune, a na plochu, ke které patří (S = dotyk)',
  'a flat face onto a flat face (facing each other)': 'rovná plocha na rovnou plochu (proti sobě)', 'a flat face facing another one, a distance apart': 'rovná plocha proti jiné, v dané vzdálenosti',
  'two flat faces in one plane, facing the same way': 'dvě rovné plochy v jedné rovině, stejným směrem',
  'two round faces on one axis (a pin in a hole, a shaft in a bearing)': 'dvě válcové plochy na jedné ose (čep v díře, hřídel v ložisku)',
  'two flat faces parallel (it only turns)': 'dvě rovné plochy rovnoběžně (jen natočí)', Turn: 'Natočení', Joints: 'Vazby',
  'Slide to any angle — it catches at 0, ±90 and ±180°. Type an exact one in the box.': 'Posuňte na libovolný úhel — chytá se na 0, ±90 a ±180°. Přesný úhel napište do políčka.',
  '🔗 Join it to another part': '🔗 Spojit s jiným dílem', 'Not joined to anything — it stays where you put it.': 'Není s ničím spojený — zůstává, kam jste ho dali.',
  'Turn it the other way round': 'Otočit opačně', 'Remove this joint (the part stays where it is)': 'Odebrat vazbu (díl zůstane, kde je)',
  'Not joined: the other part already hangs on this one — join them the other way round.': 'Nespojeno: druhý díl už visí na tomto — spojte je obráceně.',
  'Moved by hand — its joints are removed (the parts joined onto it still follow it).': 'Posunuto rukou — jeho vazby jsou odebrány (díly spojené s ním ho dál následují).',
  'Now a face of the other part.': 'Teď plochu druhého dílu.', 'Click a round face (a hole, a pin).': 'Klikněte na válcovou plochu (díru, čep).', 'Click a flat face.': 'Klikněte na rovnou plochu.',
  'Insert parts of this project (3D models and quick parts) with ＋ Insert part, then join them with 🔗 Joint.': 'Vložte díly projektu (3D modely i rychlé díly) přes ＋ Vložit díl a spojte je přes 🔗 Vazba.',
  offset: 'odsazení', gap: 'mezera', 'Esc cancels.': 'Esc ruší.',
  '🔩 Fasteners': '🔩 Spojovací prvky', 'Screws, heat-set inserts and pins where holes line up across parts — suggested, added with one click': 'Šrouby, zalisovací matice a kolíky tam, kde díry lícují přes díly — navržené, přidané jedním klikem',
  'Where holes line up through two parts, a screw (with a heat-set insert in the part below), a screw alone or a pin fits. Hover a suggestion to see its holes; Add puts it in, held by joints (it follows the parts).': 'Kde díry lícují přes dva díly, hodí se šroub (se zalisovací maticí ve spodním dílu), samotný šroub nebo kolík. Najetím na návrh uvidíte jeho díry; Přidat ho vloží, drží ho vazby (sleduje díly).',
  'No holes line up between parts yet.': 'Mezi díly zatím žádné díry nelícují.', Add: 'Přidat', Close: 'Zavřít',
  'Put a hole in each part where they are to be fastened — e.g. Ø3.4 for an M3 screw in the top part and Ø4.0 for an M3 insert in the part below — join the parts, then look here again.': 'Udělejte díru v každém dílu, kde se mají spojit — např. Ø3,4 pro šroub M3 v horním dílu a Ø4,0 pro matici M3 ve spodním — spojte díly a podívejte se sem znovu.',
  'Slide to change it — the part follows': 'Posuňte pro změnu — díl se přizpůsobí',
  'A locked joint 🔒 holds this part — unlock it in the joints list to move the part by hand.': 'Díl drží zamčená vazba 🔒 — odemkněte ji v seznamu vazeb, chcete-li díl posunout rukou.',
  'Moving it by hand breaks its {n} joint(s). Break them and move it?': 'Posunutí rukou zruší jeho vazby ({n}). Zrušit je a posunout?',
  'Locked: moving the part by hand cannot break it — click to unlock': 'Zamčeno: posunutí dílu rukou ji nezruší — kliknutím odemknete',
  'Lock it: then it cannot be broken by moving the part': 'Zamknout: pak ji posunutí dílu nezruší', 'Turn the part about this joint (about the axis, or on the face)': 'Natočit díl kolem této vazby (kolem osy nebo na ploše)',
  '{v} is the most that works here (with what is around it).': '{v} je nejvíc, co tu jde (podle toho, co je kolem).',
  'two flat faces at right angles (it only turns)': 'dvě rovné plochy v pravém úhlu (jen natočí)', 'two flat faces at an angle you set (it only turns)': 'dvě rovné plochy pod zadaným úhlem (jen natočí)',
  'a round face touching a flat face (a roller on a plate)': 'válcová plocha se dotýká rovné (váleček na desce)',
  'click where it goes in: a flat face (the holes are drilled for it, through the parts below) or a hole that is there': 'klikněte, kudy se vkládá: na rovnou plochu (díry se pro něj vyvrtají skrz díly pod ní) nebo do díry, která tam je',
  'Click the other kind of face (round ↔ flat).': 'Klikněte na druhý druh plochy (válcová ↔ rovná).', 'Click a round or a flat face.': 'Klikněte na válcovou nebo rovnou plochu.',
  'Click a flat face or a hole.': 'Klikněte na rovnou plochu nebo díru.', 'A screw goes in at a flat face.': 'Šroub se vkládá na rovné ploše.',
  '🔩 Screw / pin through parts': '🔩 Šroub / kolík skrz díly', '🔩 Screw / pin through parts…': '🔩 Šroub / kolík skrz díly…',
  'It goes in at the point on {part} and straight through the parts under it. Adding it drills the holes into those parts.': 'Vloží se v bodě na dílu {part} a projde rovně díly pod ním. Přidáním se do těch dílů vyvrtají díry.',
  What: 'Co', 'X, Y from the middle of the face — or click another point.': 'X, Y od středu plochy — nebo klikněte na jiný bod.', Through: 'Skrz', through: 'průchozí',
  '{d} mm deep': 'hloubka {d} mm', Holes: 'Díry', 'Screw + nut': 'Šroub + matice', 'Screw + heat-set insert': 'Šroub + zalisovací matice', Pin: 'Kolík',
  'Size is one of {list}.': 'Velikost je jedna z {list}.', 'There is no part at this point.': 'V tomto bodě není žádný díl.',
  '{part} is not a 3D model, so it cannot be drilled — make it a 3D model to put a screw through it.': '{part} není 3D model, nedá se vrtat — udělejte z něj 3D model, chcete-li jím prostrčit šroub.',
  'Under this point there is only {part} — join the parts first (they have to touch), then put the screw through them.': 'Pod tímto bodem je jen {part} — nejdřív díly spojte (musí se dotýkat), pak jimi prostrčte šroub.',
  'The parts are only {t} mm thick — too thin for a pin.': 'Díly mají jen {t} mm — na kolík moc tenké.',
  '{part} is {t} mm thick here — an {size} insert needs {need} mm. Use a screw + nut.': '{part} má tu tloušťku {t} mm — zalisovací matice {size} potřebuje {need} mm. Použijte šroub + matici.',
  'No standard {size} screw ends in the insert here ({t} mm to it) — use a screw + nut.': 'Žádný běžný šroub {size} tu nekončí v zalisovací matici ({t} mm k ní) — použijte šroub + matici.',
  'The parts are {t} mm thick — more than the longest {size} screw ({max} mm) holds with its nut.': 'Díly mají {t} mm — víc, než udrží nejdelší šroub {size} ({max} mm) s maticí.',
  'This point is off the face — move it back onto it.': 'Tento bod je mimo plochu — vraťte ho na ni.', 'Hole for {what}': 'Díra pro {what}',
  'Added {what} — its holes are drilled into {parts} (a hole step in each part; Ctrl+Z takes it all back).': 'Přidáno {what} — díry jsou vyvrtané do {parts} (krok Díra v každém dílu; Ctrl+Z vše vrátí).',
  'A new one': 'Nový', 'Put a screw (with a nut or an insert) or a pin through parts that have no holes yet: click where it goes in — the holes are drilled for it.': 'Prostrčte šroub (s maticí nebo zalisovací maticí) nebo kolík díly, které ještě nemají díry: klikněte, kudy se vkládá — díry se pro něj vyvrtají.',
  '⇋ Mirror': '⇋ Zrcadlit', Mirror: 'Zrcadlit', 'Mirror the part (or one step) across a base plane or a flat face — as a copy, or moved': 'Zrcadlit díl (nebo jeden krok) podle základní roviny nebo rovné plochy — jako kopii, nebo přesunout',
  'left ↔ right': 'vlevo ↔ vpravo', 'front ↔ back': 'vpředu ↔ vzadu', 'top ↔ bottom': 'nahoře ↔ dole', 'or click a flat face to mirror across it.': 'nebo klikněte na rovnou plochu, podle které se zrcadlí.',
  'Across the face you clicked (click another one to change it).': 'Podle plochy, na kterou jste klikli (kliknutím na jinou ji změníte).', 'The whole part': 'Celý díl', Across: 'Podle',
  '⇋ Mirror and copy': '⇋ Zrcadlit a kopírovat', '↦ Mirror only': '↦ Jen zrcadlit', 'The part and its mirror image, joined.': 'Díl a jeho zrcadlový obraz, spojené.',
  'The part turned into its mirror image.': 'Díl převrácený na svůj zrcadlový obraz.', 'The step is copied to the other side (holes stay holes).': 'Krok se zkopíruje na druhou stranu (díry zůstanou dírami).',
  'Mirror — choose the plane, or click a flat face to mirror across it. Enter = OK, Esc = Cancel.': 'Zrcadlit — vyberte rovinu, nebo klikněte na rovnou plochu, podle které se zrcadlí. Enter = OK, Esc = Zrušit.',
  'Click a flat face — it mirrors across it.': 'Klikněte na rovnou plochu — zrcadlí se podle ní.', '⇋ Mirror across this face': '⇋ Zrcadlit podle této plochy',
  'The mirror image changes nothing — it lands on the part itself (already symmetric there) or outside it. Choose another plane.': 'Zrcadlový obraz nic nezmění — padne na díl samotný (tam už je souměrný) nebo mimo něj. Vyberte jinou rovinu.',
  'There is no solid yet to mirror.': 'Zatím není co zrcadlit.', 'the part': 'díl', moved: 'přesunuto', copy: 'kopie', 'a face': 'plocha',
  Mirrored: 'Zrcadleně', 'Mirror shapes across a line or the X / Y axis — a copy that stays the mirror image, or moved': 'Zrcadlit tvary podle čáry nebo osy X / Y — kopie, která zůstane zrcadlovým obrazem, nebo přesunout',
  'Mirror: click the shapes to mirror (a rectangle or a joined outline goes whole). Esc = done.': 'Zrcadlit: klikněte na tvary ke zrcadlení (obdélník nebo spojený obrys celý). Esc = hotovo.',
  'Mirror: click the line to mirror across — or choose the X / Y axis in the box.': 'Zrcadlit: klikněte na čáru, podle které se zrcadlí — nebo v okénku vyberte osu X / Y.',
  'Across the Y axis (left ↔ right).': 'Podle osy Y (vlevo ↔ vpravo).', 'Across the X axis (up ↔ down).': 'Podle osy X (nahoře ↔ dole).', 'Across the line you clicked.': 'Podle čáry, na kterou jste klikli.',
  'Across:': 'Podle:', 'Y axis': 'Osa Y', 'X axis': 'Osa X', 'up ↔ down': 'nahoře ↔ dole', 'or click a line of the sketch.': 'nebo klikněte na čáru skici.',
  'Move (do not keep the original)': 'Přesunout (původní nezachovat)', Done: 'Hotovo',
  'Click a line to mirror across — or choose the X / Y axis.': 'Klikněte na čáru, podle které se zrcadlí — nebo vyberte osu X / Y.',
  'Click a line, circle or arc to mirror.': 'Klikněte na čáru, kružnici nebo oblouk ke zrcadlení.', 'A picture outline cannot be mirrored yet.': 'Obrys z obrázku zatím nejde zrcadlit.',
  '▣ Solid from a file': '▣ Těleso ze souboru', 'Add a STEP / STL / OBJ solid: joined to the part, cut out of it (a cavity it fits in), or as a see-through reference to build around': 'Přidat těleso STEP / STL / OBJ: spojené s dílem, vyříznuté z něj (dutina, do které padne), nebo průhledné jako reference, kolem které stavíte',
  '▣ Joined': '▣ Spojit', '⬚ Cut out': '⬚ Vyříznout', '👁 Reference': '👁 Reference', joined: 'spojeno', 'cut out': 'vyříznuto', reference: 'reference',
  'Part of the part: sketch on its faces, drill it, round its edges.': 'Součást dílu: skicujte na jeho plochách, vrtejte, zaoblujte hrany.',
  'Cut out of the part: a cavity it fits in exactly (e.g. inside a cover you built around it).': 'Vyříznuto z dílu: dutina, do které přesně padne (např. uvnitř krytu, který jste kolem něj postavili).',
  'Shown see-through, not part of the part: build around it — a cover, a holder — then Cut out a copy of it to make it fit.': 'Zobrazeno průhledně, není součástí dílu: stavte kolem něj — kryt, držák — pak jeho kopii Vyřízněte, aby lícoval.',
  'Solid from a file — joined to the part, cut out of it, or a see-through reference. Enter = OK, Esc = Cancel.': 'Těleso ze souboru — spojit s dílem, vyříznout z něj, nebo průhledná reference. Enter = OK, Esc = Zrušit.',
  'The file of an imported solid is not on this computer — open the project file (it carries the file) again.': 'Soubor importovaného tělesa na tomto počítači není — otevřete znovu soubor projektu (soubor nese).',
  'This mesh is too big to become an exact solid — it opens as a quick part (sliced), as before.': 'Tato síť je příliš velká na přesné těleso — otevře se jako rychlý díl (rozřezaný), jako dřív.',
  '{name} is open as a 3D model ({faces} faces) — sketch on its faces, add holes, or ask the AI to build on it.': '{name} je otevřený jako 3D model ({faces} ploch) — skicujte na jeho plochách, přidejte díry, nebo ať na něm staví AI.',
  '📂 From a file (STEP / STL / OBJ)…': '📂 Ze souboru (STEP / STL / OBJ)…', 'There is nothing to cut it out of yet — make the part first (or show it as a reference).': 'Zatím není z čeho vyříznout — nejdřív udělejte díl (nebo ho zobrazte jako referenci).',
  'Distance along the axis between the facing ends of the two round faces (e.g. two plates 30 mm apart). Empty: it slides freely.': 'Vzdálenost po ose mezi přivrácenými konci obou válcových ploch (např. dvě desky 30 mm od sebe). Prázdné: volně klouže.',
  free: 'volně', 'Its turn about the axis is locked — click to let it turn freely': 'Natočení kolem osy je zamčené — kliknutím ho uvolníte',
  'Lock its turn about the axis (where it is now)': 'Zamknout natočení kolem osy (jak je teď)',
  Colour: 'Barva', 'See-through': 'Průhlednost', 'Its colour here and in assemblies': 'Jeho barva zde i v sestavách', Look: 'Vzhled',
  'Its own look in this assembly.': 'Vlastní vzhled v této sestavě.', "As its part (set in the part's panel).": 'Jako jeho díl (nastavuje se v panelu dílu).',
  'The assembly colours.': 'Barvy sestavy.', '↺ As its part': '↺ Jako díl',
  copy: 'kopie', '⧉ Duplicate as a new part': '⧉ Duplikovat jako nový díl', '⧉ Make it its own part': '⧉ Udělat z něj vlastní díl',
  'A copy of this 3D model as a new part of its own (its own tab) — change it without changing this one': 'Kopie tohoto 3D modelu jako samostatný nový díl (vlastní záložka) — měňte ji bez změny tohoto',
  'Copy its part as a new part of the project and use the copy here — then it can be changed alone (the other copies stay as they are)': 'Zkopírovat jeho díl jako nový díl projektu a použít kopii zde — pak jde měnit samostatně (ostatní kopie zůstanou)',
  '{name} — a copy of its own (change it without changing the original).': '{name} — samostatná kopie (měňte ji bez změny originálu).',
  '{inst} now has a part of its own: {name} — change it without changing the others.': '{inst} má teď vlastní díl: {name} — měňte ho bez změny ostatních.',
  'Measure: click a spot (a face, a corner), then another one — the distance; two parallel flat faces: the gap between them; two round faces: how far apart their axes are': 'Měření: klikněte na místo (plochu, roh), pak na další — vzdálenost; dvě rovnoběžné rovné plochy: mezera mezi nimi; dvě válcové plochy: vzdálenost jejich os',
  'Measure — click a spot, then another one (corners snap). Esc ends.': 'Měření — klikněte na místo, pak na další (rohy se chytají). Esc končí.',
  Of: 'Díl', Corner: 'Roh', 'Faces apart': 'Plochy od sebe', 'Axes apart': 'Osy od sebe',
  Edit: 'Úpravy', '✎ Edit it here': '✎ Upravit zde', '🔓 Editable from here': '🔓 Lze upravit odsud', '🔒 Locked': '🔒 Zamčeno',
  'Change its part in the 3D modeler, the rest of the assembly see-through around it (or double-click it)': 'Upravit jeho díl ve 3D modeláři, zbytek sestavy průhledně kolem (nebo na něj dvakrát klikněte)',
  'Lock it: its part cannot be changed from this assembly': 'Zamknout: jeho díl nepůjde z této sestavy změnit', 'Unlock it to change its part from this assembly': 'Odemkněte, chcete-li jeho díl měnit z této sestavy',
  'Every copy of its part changes (here and in other assemblies).': 'Změní se každá kopie jeho dílu (zde i v jiných sestavách).',
  'Unlock it to change its part from here — locked, it cannot be changed by accident.': 'Odemkněte, chcete-li jeho díl měnit odsud — zamčený ho nezměníte omylem.',
  'Only 3D model parts can be changed here — open a quick part in its own tab.': 'Zde lze měnit jen 3D modely — rychlý díl otevřete v jeho záložce.',
  'Editing this part from the assembly is locked — 🔓 unlock it in its panel first.': 'Úpravy tohoto dílu ze sestavy jsou zamčené — nejdřív ho 🔓 odemkněte v jeho panelu.',
  'Editing it in': 'Upravujete ho v', 'the other parts are see-through; changes show in the assembly.': 'ostatní díly jsou průhledné; změny se projeví v sestavě.',
  'Back to the assembly': 'Zpět do sestavy',
  '🎨 Paint': '🎨 Obarvit', 'Colour faces, or whole bodies of an imported file: click them (Ctrl+click: more), then pick a colour': 'Obarvit plochy nebo celá tělesa importovaného souboru: klikněte na ně (Ctrl+klik: další), pak vyberte barvu',
  'Paint — click a face (or a body), Ctrl+click for more, then pick a colour. Esc ends.': 'Obarvit — klikněte na plochu (nebo těleso), Ctrl+klik pro další, pak vyberte barvu. Esc končí.',
  '▢ Faces': '▢ Plochy', '▣ Bodies': '▣ Tělesa', 'This part is one body': 'Tento díl je jedno těleso', 'Nothing chosen yet': 'Zatím nic nevybráno',
  'Click a face — Ctrl+click adds more (or takes one away).': 'Klikněte na plochu — Ctrl+klik přidá další (nebo jednu ubere).',
  'Click a body — Ctrl+click adds more (or takes one away).': 'Klikněte na těleso — Ctrl+klik přidá další (nebo jedno ubere).',
  '{n} face(s) chosen': 'vybráno ploch: {n}', '↺ Their own colour off': '↺ Zrušit jejich barvu', 'Clear all colours': 'Smazat všechny barvy',
  '{n} face(s) of this part have their own colour (shown in assemblies too).': 'Vlastní barvu má ploch tohoto dílu: {n} (vidět i v sestavách).',
  'Rename this step': 'Přejmenovat tento krok', 'Rename its part (its tab too)': 'Přejmenovat jeho díl (i záložku)',
  'Auto3DModeler — created by Rafiontech (rafiontech.cz)': 'Auto3DModeler — vytvořil Rafiontech (rafiontech.cz)', by: 'od',
  "Keep the file's colours": 'Zachovat barvy ze souboru',
  '🪄 Auto-dimension': '🪄 Automatické kóty', 'Lock the sizes the sketch still needs to be fully defined: each shape sized, and placed from the nearest edges of the part (or the origin)': 'Zamknout rozměry, které skice ještě chybí k úplnému určení: každý tvar okótovaný a umístěný od nejbližších hran dílu (nebo od počátku)',
  'Auto-dimension needs the sketch solver.': 'Automatické kóty potřebují řešič skic.', 'The sketch does not solve as it is — fix it first.': 'Skica se takto nedá vyřešit — nejdřív ji opravte.',
  'The sketch is fully defined already.': 'Skica už je úplně určená.', '{n} size(s) locked — the sketch is fully defined.': 'Zamčeno rozměrů: {n} — skica je úplně určená.',
  '{n} size(s) locked — {k} still free (lock them by hand, or add relations).': 'Zamčeno rozměrů: {n} — volných zbývá {k} (zamkněte je ručně nebo přidejte vazby).',
  'click 👁 to show / hide': 'klikněte na 👁 pro zobrazení / skrytí', '⬚ Select': '⬚ Vybrat', '／ Line': '／ Čára', '◯ Circle': '◯ Kružnice', '⤢ Fit': '⤢ Celé',
  'Click a shape (Ctrl+click: more), Delete removes it; drag the paper to move it, the wheel zooms': 'Klikněte na tvar (Ctrl+klik: další), Delete ho smaže; tažením papíru posunete, kolečkem přiblížíte',
  'Draw lines (L) — ends, middles and centres snap': 'Kreslit čáry (L) — chytají se konce, středy a středy kružnic', 'Draw a circle: its centre, then a point on it (C)': 'Nakreslit kružnici: střed, pak bod na ní (C)',
  'Measure: two spots, or a circle for its Ø (M)': 'Měření: dvě místa, nebo kružnice pro její Ø (M)', 'Show all of it (F)': 'Zobrazit celé (F)', 'What to make of the drawing (its shown layers)': 'Co z výkresu udělat (z jeho zobrazených hladin)',
  'Use ▾': 'Použít ▾', '✏ As a sketch of a new 3D model': '✏ Jako skicu nového 3D modelu', '▤ As a quick part (its closed outlines)': '▤ Jako rychlý díl (z uzavřených obrysů)',
  'As a sketch of a new 3D model': 'Jako skicu nového 3D modelu', 'As a quick part (its closed outlines)': 'Jako rychlý díl (z uzavřených obrysů)',
  'Line: click where it starts, then where it ends (it goes on from there; Esc = stop).': 'Čára: klikněte, kde začíná, pak kde končí (pokračuje odtud; Esc = konec).',
  'Circle: click the centre, then a point on it.': 'Kružnice: klikněte na střed, pak na bod na ní.', 'Measure: click two spots (ends, middles and centres snap) — or a circle for its Ø.': 'Měření: klikněte na dvě místa (chytají se konce, středy) — nebo na kružnici pro její Ø.',
  end: 'konec', middle: 'střed', centre: 'střed', From: 'Od', 'click the second spot.': 'klikněte na druhé místo.', Arc: 'Oblouk', Polyline: 'Lomená čára',
  'Show this layer': 'Zobrazit hladinu', 'Hide this layer': 'Skrýt hladinu', "The layer's colour": 'Barva hladiny', 'Click: new lines go on this layer': 'Klik: nové čáry půjdou do této hladiny',
  All: 'Vše', None: 'Nic', Layer: 'Hladina', Layers: 'Hladiny', Shapes: 'Tvary', 'What next': 'Co dál', closed: 'uzavřená', '{n} points': '{n} bodů', '{n} shapes': '{n} tvarů',
  'Look, measure, tidy it up — then Use ▾ makes something of the shown layers:': 'Prohlédněte, změřte, upravte — pak z zobrazených hladin udělá něco Použít ▾:',
  '{name}: {n} shapes on {k} layers — look, measure, tidy it up; Use ▾ makes a sketch or a quick part of it.': '{name}: {n} tvarů v {k} hladinách — prohlédněte, změřte, upravte; Použít ▾ z něj udělá skicu nebo rychlý díl.',
  'Nothing to sketch on the shown layers.': 'V zobrazených hladinách není co skicovat.', 'A big sketch — hide the layers you do not need first, it is quicker to work with.': 'Velká skica — nejdřív skryjte hladiny, které nepotřebujete, pracuje se s ní rychleji.',
  'The drawing is the sketch of a new 3D model — edit it, or ⬆ Extrude it.': 'Výkres je skicou nového 3D modelu — upravte ji, nebo ji ⬆ Vysuňte.',
  'File units': 'Jednotky souboru', 'What one unit of the file is — the file may not say (or say it wrong): change it and the drawing is rescaled': 'Čemu odpovídá jedna jednotka souboru — soubor to nemusí uvádět (nebo špatně): změnou se výkres přepočítá',
  'The file does not say its units and is only a few mm big — if it is in inches, set File units to inch (in the panel).': 'Soubor neuvádí jednotky a má jen pár mm — pokud je v palcích, nastavte v panelu Jednotky souboru na inch.',
  'These steps use it': 'Tyto kroky ho používají', 'Keep them where they are': 'Ponechat je, jak jsou', 'Delete them too': 'Smazat je také',
  'Deleted too (they cannot be without it)': 'Smazány budou i (bez něj nemohou být)',
  'A sketch keeps its place and its sizes; it no longer follows the deleted step.': 'Skica si nechá místo i rozměry; smazaný krok už nesleduje.',
  'Select by filter': 'Výběr filtrem', 'Add a filter: all of them must hold': 'Přidat filtr: platit musí všechny', Filter: 'Filtr', '{n} match': 'vyhovuje: {n}',
  'Select them': 'Vybrat je', 'Add to the selection': 'Přidat k výběru', 'Remove this filter': 'Odebrat filtr', Shape: 'Tvar', Radius: 'Poloměr', Text: 'Text',
  is: 'je', 'is not': 'není', contains: 'obsahuje', different: 'různé', 'Type it: all {n} change.': 'Napište ho: změní se všech {n}.', 'Type it: it changes.': 'Napište ho: změní se.',
  'All like this': 'Všechny takové', 'Filters for shapes like this one (its shape, layer and size) — and select them all': 'Filtry pro tvary jako tento (tvar, hladina, velikost) — a vybrat je všechny',
  'The size must be greater than zero.': 'Velikost musí být větší než nula.',
  'Screw / pin': 'Šroub / kolík', 'click the hole it goes in from, then the hole in the other part — the fitting screw (and insert) or pin goes in': 'klikněte na díru, odkud se vkládá, pak na díru v druhém dílu — vloží se vhodný šroub (s maticí) nebo kolík',
  'These holes ({a}, {b}) do not line up, or fit no standard screw / pin — a screw needs a clearance hole in the part it goes in from (M3: Ø3.2–3.7) and one that fits it or an insert (M3 insert: Ø3.9–4.4) below.': 'Tyto díry ({a}, {b}) nelícují nebo neodpovídají žádnému běžnému šroubu / kolíku — šroub potřebuje průchozí díru v dílu, odkud se vkládá (M3: Ø3,2–3,7), a pod ní díru pro něj nebo pro matici (matice M3: Ø3,9–4,4).',
  '⟂ Relations ▾': '⟂ Vazby ▾', Relations: 'Vazby', Horizontal: 'Vodorovně', Vertical: 'Svisle', Perpendicular: 'Kolmo', Equal: 'Stejně',
  Concentric: 'Soustředně', Coincident: 'Totožně', Tangent: 'Tečně', Fix: 'Ukotvit', 'click to remove it': 'kliknutím odeberete', 'Remove this relation': 'Odebrat tuto vazbu',
  'Make shapes keep a relation: horizontal, vertical, parallel, perpendicular, equal, concentric, coincident, tangent, fixed': 'Tvary drží vazbu: vodorovně, svisle, rovnoběžně, kolmo, stejně, soustředně, totožně, tečně, ukotveně',
  'two lines (same length) or two circles / arcs (same size)': 'dvě čáry (stejná délka) nebo dvě kružnice / oblouky (stejná velikost)',
  'a point, then another point, a line or a circle it lies on': 'bod, pak jiný bod, čára nebo kružnice, na které leží',
  'a line or a circle / arc, then a circle / arc it touches': 'čára nebo kružnice / oblouk, pak kružnice / oblouk, kterého se dotýká',
  'a point that stays where it is': 'bod, který zůstane, kde je', 'Equal: two lines, or two circles / arcs.': 'Stejně: dvě čáry, nebo dvě kružnice / oblouky.',
  'These relations contradict each other (a line or circle would shrink to nothing) — remove one of them first.': 'Tyto vazby si odporují (čára nebo kružnice by se zmenšila na nic) — nejdřív jednu odeberte.',
  // language switch
  'Čeština / English': 'Čeština / English',
};

// ---------------------------------------------------------------------------- texts with values ({} = a value; {1}, {2} … in the Czech text)
const CS_PATTERNS = [
  ['Slicing {} / {}', 'Řezání {1} / {2}'], ['Uploading {}…', 'Nahrávám {1}…'], ['Reading {}', 'Čtu {1}'], ['Reading the STEP file (tessellating)', 'Čtu soubor STEP (triangulace)'],
  ['Drawing read with {} — review the highlighted dimensions.', 'Výkres načten s {1} — zkontrolujte zvýrazněné rozměry.'],
  ['{} error(s)', '{1} chyb(a)'], ['{} warning(s)', '{1} varování'], ['{} error(s) and {} warning(s)', '{1} chyb(a) a {2} varování'],
  ['Change not applied: {}', 'Změna nebyla použita: {1}'], ['Limit reached: {}', 'Dosažen limit: {1}'],
  ['{} triangles', '{1} trojúhelníků'], ['volume {}', 'objem {1}'], ['{} cutout(s)', '{1} výřez(ů)'], ['{} design layer(s)', '{1} vrstev designu'], ['{} object(s)', '{1} objekt(ů)'],
  ['{} change(s) from the drawing', '{1} změn(a) oproti výkresu'],
  ['Restore all dimensions to the drawing? This undoes {} change(s), including dimensions you added.', 'Obnovit všechny rozměry podle výkresu? Vrátí se {1} změn(a), včetně vámi přidaných kót.'],
  ['drawing: “{}”', 'výkres: „{1}“'], ['invalid label “{}”', 'neplatný popis „{1}“'], ['{} removed.', '{1} odebráno.'], ['{} now drives the geometry.', '{1} nyní řídí geometrii.'],
  ['Read {} dimension(s) from the drawing; outline with {} cutout(s).', 'Z výkresu načteno {1} kót; obrys s {2} výřezy.'],
  ['3D design — {}', '3D design — {1}'], ['{} — Esc cancels', '{1} — Esc zruší'],
  ['Click on the part where “{}” goes', 'Klikněte na díl, kam patří „{1}“'], ['Click on the part where the {} goes', 'Klikněte na díl, kam patří {1}'],
  ['Click a point, hole, cylinder or face — the first point of {}', 'Klikněte na bod, díru, válec nebo plochu — první bod {1}'],
  ['Click the second point of {} (Esc = keep just the first)', 'Klikněte na druhý bod {1} (Esc = ponechat jen první)'],
  ['Could not use that image: {}', 'Obrázek nelze použít: {1}'], ['Could not open the picture: {}', 'Obrázek nelze otevřít: {1}'],
  ['“{}” is part of the {} preset — use “Edit as 3D objects →” in the Part tab to change or delete it.', '„{1}“ je součástí předvolby {2} — pro změnu nebo smazání použijte „Upravit jako 3D objekty →“ v záložce Díl.'],
  ['Selected “{}” — Delete removes it, Esc deselects.', 'Vybráno „{1}“ — Delete smaže, Esc zruší výběr.'],
  ['Exported {} (in mm). Note: {} unresolved check(s) — estimated values may be wrong.', 'Exportováno {1} (v mm). Pozor: {2} nevyřešených kontrol — odhadnuté hodnoty mohou být chybné.'],
  ['Exported {} (in mm).', 'Exportováno {1} (v mm).'], ['Export failed: {}', 'Export selhal: {1}'],
  ['Project “{}” from {} — click to rename', 'Projekt „{1}“ z {2} — klikněte pro přejmenování'], ['Project renamed to “{}”.', 'Projekt přejmenován na „{1}“.'],
  ['Project saved as {}.', 'Projekt uložen jako {1}.'],
  ['hole Ø {} · {}', 'díra Ø {1} · {2}'], ['cylinder Ø {} · {}', 'válec Ø {1} · {2}'], ['top face {} · {}', 'horní plocha {1} · {2}'], ['bottom face {} · {}', 'spodní plocha {1} · {2}'],
  ['corner · {}', 'roh · {1}'], ['edge · {}', 'hrana · {1}'], ['wall · {}', 'stěna · {1}'],
  ['Top face at z {}', 'Horní plocha v z {1}'], ['Bottom face at z {}', 'Spodní plocha v z {1}'], ['Keep the Ø {} as a dimension:', 'Ponechat Ø {1} jako kótu:'],
  ['📏 {} mm (Δx {}, Δy {})', '📏 {1} mm (Δx {2}, Δy {3})'], ['{} px = {} mm', '{1} px = {2} mm'],
  ['Size: {} × {} × {} mm', 'Velikost: {1} × {2} × {3} mm'], ['Width follows the text: {} mm. Height is the height of the whole text block.', 'Šířka se řídí textem: {1} mm. Výška je výška celého bloku textu.'],
  ['＋ {} band', '＋ Pás {1}'], ['The {}, grown or shrunk by an offset, extruded', '{1} zvětšený nebo zmenšený o odsazení a vytažený'],
  ['A wall along the {}: the area between two offsets', 'Stěna podél {1}: oblast mezi dvěma odsazeními'], ['2D shapes on the {}', '2D tvary na {1}'],
  ['Added to or cut from the {} itself before anything is built.', 'Přidávají se k {1} nebo se z něj vyřezávají ještě před sestavením.'],
  ['Added to or cut from the {} itself before anything is built — a cookie cutter wall follows them too.', 'Přidávají se k {1} nebo se z něj vyřezávají ještě před sestavením — stěna vykrajovátka je také sleduje.'],
  ['{} — click on the part (corners and face heights snap)', '{1} — klikněte na díl (rohy a výšky ploch se přichytí)'], ['{} copy', '{1} kopie'],
  ['Claude is {}…', 'Claude {1}…'], ['Claude Code connected · {}', 'Claude Code připojen · {1}'], ['Retrying ({})…', 'Opakuji ({1})…'],
  ['Slanted / curved walls are built in {} slices of {} mm.', 'Šikmé / zakřivené stěny jsou sestaveny ze {1} řezů po {2} mm.'],
  ['Slanted / curved walls are built in {} slices of {} mm (chosen so the part builds quickly — a smaller slice height in the Part tab gives a finer result).', 'Šikmé / zakřivené stěny jsou sestaveny ze {1} řezů po {2} mm (zvoleno, aby se díl sestavil rychle — menší výška řezu v záložce Díl dá jemnější výsledek).'],
  ['Slanted or curved walls are built as steps of {} mm (set a smaller slice height for a finer result).', 'Šikmé nebo zakřivené stěny jsou sestaveny jako schody po {1} mm (menší výška řezu dá jemnější výsledek).'],
  ['The outline consists of {} separate pieces.', 'Obrys se skládá z {1} samostatných kusů.'], ['{} is empty (an inward offset larger than the shape?).', '{1} je prázdný (odsazení dovnitř větší než tvar?).'],
  ['{}: the top ({} mm) must be above the bottom ({} mm).', '{1}: horní hrana ({2} mm) musí být nad spodní ({3} mm).'],
  ['{}: the outer offset must be larger than the inner offset.', '{1}: vnější odsazení musí být větší než vnitřní.'],
  ['{} has walls thinner than 0.4 mm that may not print.', '{1} má stěny tenčí než 0,4 mm, které se nemusí vytisknout.'],
  ['{} must be greater than zero (got {}).', '{1} musí být větší než nula (je {2}).'],
  ['{}: has no effect — it lies outside the face (check its mask, position and margin).', '{1}: nemá žádný účinek — leží mimo plochu (zkontrolujte masku, polohu a okraj).'],
  ['{}: contains features thinner than {} mm that may not 3D-print (increase line width / spacing).', '{1}: obsahuje prvky tenčí než {2} mm, které se nemusí vytisknout (zvětšete šířku čar / rozestup).'],
  ['{}: engrave depth {} is not less than the thickness {} — use \'Cut through\' instead.', '{1}: hloubka rytí {2} není menší než tloušťka {3} — použijte raději „Prořezat“.'],
  ['The drawing does not specify a thickness (e.g. \'t=18mm\'). A default of {} was used — set the real thickness.', 'Výkres neuvádí tloušťku (např. „t=18mm“). Použita výchozí hodnota {1} — nastavte skutečnou tloušťku.'],
  ['{}: {}. Estimated {} from the drawing proportions — please verify and enter the correct value.', '{1}: {2}. Odhadnuto {3} z proporcí výkresu — ověřte a zadejte správnou hodnotu.'],
  ['The drawing is not to scale (between {} and {} pt per {}). The model is built from the dimension values; proportions are used only for missing values.', 'Výkres není v měřítku ({1} až {2} pt na {3}). Model se sestaví z hodnot kót; proporce se použijí jen pro chybějící hodnoty.'],
  ['{} ({}) is already determined by other dimensions; shown as a reference value.', '{1} ({2}) je již určena jinými kótami; zobrazena jako referenční hodnota.'],
  ['Dimension {} does not quite touch the geometry ({} pt gap); snapped to the nearest edge.', 'Kóta {1} se úplně nedotýká geometrie (mezera {2} pt); přichycena k nejbližší hraně.'],
  ['Dimension {} has no unit; assumed {}.', 'Kóta {1} nemá jednotku; předpokládáno {2}.'], ['Dimension {} does not point at any edge of the part and was ignored.', 'Kóta {1} nemíří na žádnou hranu dílu a byla ignorována.'],
  ['Edges at the same drawn position were assumed to be aligned ({} = 0). Change it if they should be offset.', 'Hrany ve stejné nakreslené poloze byly považovány za zarovnané ({1} = 0). Změňte, pokud mají být posunuté.'],
  ['{} curved outline segment(s) (arcs/circles) were found; only straight-line outlines are supported, curves were ignored.', 'Nalezeno {1} zakřivených úseků obrysu (oblouky / kružnice); podporovány jsou jen přímé obrysy, křivky byly ignorovány.'],
  ['{} open line(s) in the drawing do not form a closed outline and were ignored.', '{1} otevřených čar ve výkresu netvoří uzavřený obrys a byly ignorovány.'],
  ['Cutout {} width', 'Šířka výřezu {1}'], ['Cutout {} height', 'Výška výřezu {1}'], ['Cutout {} from left edge', 'Výřez {1} od levého okraje'], ['Cutout {} from right edge', 'Výřez {1} od pravého okraje'],
  ['Cutout {} from bottom edge', 'Výřez {1} od spodního okraje'], ['Cutout {} from top edge', 'Výřez {1} od horního okraje'], ['Outline width {}', 'Šířka obrysu {1}'], ['Outline height {}', 'Výška obrysu {1}'],
  ['Cutout {} ↔ cutout {} spacing', 'Rozteč výřezů {1} ↔ {2}'], ['Cutout {} ↔ cutout {} vertical spacing', 'Svislá rozteč výřezů {1} ↔ {2}'], ['Cutout {}', 'Výřez {1}'],
  ['Horizontal distance {}', 'Vodorovná vzdálenost {1}'], ['Vertical distance {}', 'Svislá vzdálenost {1}'], ['Dimension {}', 'Kóta {1}'], ['Dimension {} (X)', 'Kóta {1} (X)'],
  ['Dimension {} (Y)', 'Kóta {1} (Y)'], ['Dimension {} (Z)', 'Kóta {1} (Z)'],
  ['Inner radius {} {} (from the length and angle).', 'Vnitřní poloměr {1} {2} (z délky a úhlu).'], ['Position ({})', 'Poloha ({1})'], ['Inner radius ({})', 'Vnitřní poloměr ({1})'],
  ['Height ({})', 'Výška ({1})'], ['Depth ({})', 'Hloubka ({1})'], ['Centre ({})', 'Střed ({1})'], ['Size ({})', 'Velikost ({1})'], ['Edge margin ({})', 'Okraj ({1})'],
  ['Spacing ({})', 'Rozestup ({1})'], ['Line width ({})', 'Šířka čáry ({1})'], ['Offset ({})', 'Odsazení ({1})'], ['Bend {}', 'Ohyb {1}'],
  ['Part: {} × {} × {} mm', 'Díl: {1} × {2} × {3} mm'], ['Usable plate: {} × {} × {} mm', 'Využitelná podložka: {1} × {2} × {3} mm'],
  ['Printer “{}” saved.', 'Tiskárna „{1}“ uložena.'], ['Delete printer “{}”?', 'Smazat tiskárnu „{1}“?'],
  ['{}% of picture', '{1} % obrázku'], ['found by {}', 'nalezeno: {1}'], ['{} pieces', '{1} kusů'], ['{} hole(s)', '{1} děr'], ['Build volume {} × {} × {} mm', 'Tiskový prostor {1} × {2} × {3} mm'], ['inside {}', 'uvnitř {1}'], ['not this {}', 'tohle ne {1}'],
  ['At most {} photos per message.', 'Nejvýše {1} fotek na zprávu.'], ['{} is not a photo (PNG, JPG, WEBP or GIF).', '{1} není fotka (PNG, JPG, WEBP nebo GIF).'],
  ['{} is larger than 10 MB.', '{1} je větší než 10 MB.'],
  ['on a face of {}', 'na ploše {1}'], ['cut {} mm', 'řez {1} mm'],
  ['Delete “{}”? These steps need it and are deleted too: {}.', 'Smazat „{1}“? Tyto kroky ho potřebují a smažou se také: {2}.'],
  ['⚠ {} step(s) could not be built — point at ⚠ in the list to see why.', '⚠ {1} krok(ů) nešlo sestavit — najeďte na ⚠ v seznamu a uvidíte proč.'],
  ['{} × {} × {} mm · volume {} cm³', '{1} × {2} × {3} mm · objem {4} cm³'],
  ['The 3D model workspace needs its CAD kernel: {}', 'Prostředí 3D modelu potřebuje své CAD jádro: {1}'],
  ['Could not build this step ({}).', 'Tento krok nešlo sestavit ({1}).'], ['Building took longer than {} s and was stopped.', 'Sestavování trvalo déle než {1} s a bylo zastaveno.'],
  ['“{}” must be a number.', '„{1}“ musí být číslo.'], ['Unknown feature type “{}”.', 'Neznámý typ kroku „{1}“.'],
  ['{} free — those sizes follow when you drag. Type a size (or click 🔓) to lock it.', '{1} volných — tyto rozměry se při tažení mění. Napište rozměr (nebo klikněte na 🔓) a zamknete ho.'],
  ['That does not fit the other locked sizes ({}) — unlock one of them first.', 'To nesedí s ostatními zamčenými rozměry ({1}) — nejprve jeden z nich odemkněte.'],
  ['{} must be a number.', '{1} musí být číslo.'],
  ['🔒 {} (from the part edge)', '🔒 {1} (od hrany dílu)'], ['🔒 {} (from the origin)', '🔒 {1} (od počátku)'], ['🔒 {} (from the point)', '🔒 {1} (od bodu)'],
  ['🔒 {} (on the origin)', '🔒 {1} (v počátku)'], ['🔒 Length {}', '🔒 Délka {1}'],
  ['The sketch could not be solved (server error {}).', 'Skicu nešlo vyřešit (chyba serveru {1}).'],
  ['R {} · {} edge(s)', 'R {1} · {2} hran(y)'], ['{} mm · {} edge(s)', '{1} mm · {2} hran(y)'], ['Ø{} · {} hole(s)', 'Ø{1} · {2} děr(a)'],
  ['Ø{} · {} hole(s) · {} deep', 'Ø{1} · {2} děr(a) · hloubka {3}'], ['{} edge(s) picked', 'vybráno hran: {1}'],
  ['{} edge(s) were found again by their position only — check that the right edges are rounded.', '{1} hran(y) bylo nalezeno znovu jen podle polohy — zkontrolujte, že jsou zaobleny správné hrany.'],
  ['{} edge(s) were found again by their position only — check that the right edges are bevelled.', '{1} hran(y) bylo nalezeno znovu jen podle polohy — zkontrolujte, že jsou zkoseny správné hrany.'],
  ['up to a face {} mm', 'k ploše {1} mm'], ['cut up to a face {} mm', 'řez k ploše {1} mm'], ['Up to the face {}', 'K ploše {1}'],
  ['on Top {} mm', 'na horní rovině {1} mm'], ['on Front {} mm', 'na přední rovině {1} mm'], ['on Right {} mm', 'na pravé rovině {1} mm'],
  ['{} sketches · cut', '{1} skici · řez'], ['{} sketches', '{1} skici'], ['along {} · cut', 'po {1} · řez'], ['along {}', 'po {1}'],
  ['🔗 Snapped onto {} ({}) — it follows that part.', '🔗 Přichyceno na {1} ({2}) — tento díl následuje.'], ['{} part(s) are snapped onto this one and follow it.', '{1} díl(y) jsou přichyceny na tento a následují ho.'],
  ['✎ Edit {}', '✎ Upravit {1}'], ['✕ Delete {}', '✕ Smazat {1}'], ['{} — {}', '{1} — {2}'], ['{} · {}', '{1} · {2}'],
  ['{} — it now holds (change it or ✕ it in the panel).', '{1} — teď drží (změňte nebo ✕ v panelu).'], ['{} part(s) · {} joint(s)', '{1} díl(y) · {2} vazba(y)'],
  ['{}: click a flat face of the part to move', '{1}: klikněte na rovnou plochu dílu, který se posune'], ['{}: click a round face of the part to move', '{1}: klikněte na válcovou plochu dílu, který se posune'],
  ['{}: click a flat face of the part to move (the selected one)', '{1}: klikněte na rovnou plochu dílu, který se posune (vybraného)'],
  ['{}: click a round face of the part to move (the selected one)', '{1}: klikněte na válcovou plochu dílu, který se posune (vybraného)'],
  ['{}: now click a flat face of the other part.', '{1}: teď klikněte na rovnou plochu druhého dílu.'], ['{}: now click a round face of the other part.', '{1}: teď klikněte na válcovou plochu druhého dílu.'],
  ['Add all ({})', 'Přidat vše ({1})'], ['Added {} fastener(s) — they follow the parts (each a part of the project you can open).', 'Přidáno {1} spojovacích prvků — sledují díly (každý je díl projektu, který lze otevřít).'],
  ['✓ Every hole that lines up has its fastener ({}).', '✓ Každá lícující díra má svůj spojovací prvek ({1}).'],
  ['{}: now click the other part (anywhere).', '{1}: teď klikněte na druhý díl (kamkoli).'],
  ['{}: click a round or a flat face of the part to move', '{1}: klikněte na válcovou nebo rovnou plochu dílu, který se posune'],
  ['{}: click a round or a flat face of the part to move (the selected one)', '{1}: klikněte na válcovou nebo rovnou plochu dílu, který se posune (vybraného)'],
  ['{}: click where it goes in — a point on a flat face (the holes are drilled for it), or a hole that is there. Esc cancels.', '{1}: klikněte, kudy se vkládá — bod na rovné ploše (díry se pro něj vyvrtají), nebo díra, která tam je. Esc ruší.'],
  ['{}× around', '{1}× dokola'], ['{}× · {} mm apart', '{1}× · {2} mm od sebe'], ['Line {} of the sketch', 'Čára {1} skici'], ['wall {} mm · {} open', 'stěna {1} mm · {2} otevřeno'], ['Open face {}', 'Otevřená plocha {1}'], ['{}° cut', '{1}° řez'],
  ['Height {} mm (follows the width).', 'Výška {1} mm (přizpůsobí se šířce).'], ['{} — 3D', '{1} — 3D'],
  ['{} hidden — the drawing still sets this size. Show it again in Dimensions (Hidden).', '{1} skryta — výkres tento rozměr stále určuje. Znovu ji zobrazíte v Rozměrech (Skryté).'],
  ['Show {} hidden size(s)', 'Zobrazit skryté rozměry ({1})'], ['🔓 {} (from the part edge)', '🔓 {1} (od hrany dílu)'], ['🔓 {} (from the origin)', '🔓 {1} (od počátku)'],
  ['🔓 {} (from the point)', '🔓 {1} (od bodu)'],
  ['{} — its position (where its own origin is) and turns.', '{1} — jeho poloha (kde je jeho vlastní počátek) a natočení.'], ['{} part(s)', '{1} dílů'],
  ['the dimension {}', 'kóta {1}'], ['{} (kept)', '{1} (ponecháno)'], ['{} (mm)', '{1} (mm)'],
  ['Close the part “{}”? It is removed from the project (Save project keeps the rest).', 'Zavřít díl „{1}“? Odebere se z projektu (Uložit projekt uloží zbytek).'],
  ['Part renamed to “{}”.', 'Díl přejmenován na „{1}“.'], ['Project loaded — {} parts (tabs in the top bar).', 'Projekt načten — {1} dílů (záložky v horní liště).'],
  ['This project was saved by a newer version of the app (file version {}).', 'Projekt byl uložen novější verzí aplikace (verze souboru {1}).'],
  ['Part {} in the project file has no id or a duplicate one.', 'Díl {1} v souboru projektu nemá id nebo má duplicitní.'],
  ['Part “{}” has no model in it.', 'Díl „{1}“ neobsahuje model.'],
  ['Click where the fold line goes · fold line vertical (press R to rotate, Esc to cancel)', 'Klikněte, kam patří linie ohybu · linie svislá (R = otočit, Esc = zrušit)'],
  ['Click where the fold line goes · fold line horizontal (press R to rotate, Esc to cancel)', 'Klikněte, kam patří linie ohybu · linie vodorovná (R = otočit, Esc = zrušit)'],
  ['The part is {} mm tall but the {} can only print {} mm high.', 'Díl je vysoký {1} mm, ale {2} tiskne jen do výšky {3} mm.'],
  ['Exported {} pieces as {} (mm) with an assembly sheet.', 'Exportováno {1} dílů jako {2} (mm) s montážním listem.'],
  ['Exported {} pieces + connector parts ({} to print) as {} (mm) with an assembly sheet.', 'Exportováno {1} dílů + spojovací díly ({2} k tisku) jako {3} (mm) s montážním listem.'],
  // detection methods (outline wizard)
  ['background ({} colour)', 'pozadí ({1} barva)'], ['background ({} colours)', 'pozadí ({1} barvy)'], ['colour clusters ({})', 'shluky barev ({1})'],
  ['your colours ±{}', 'vaše barvy ±{1}'], ['object colour ±{}', 'barva předmětu ±{1}'], ['background colour ±{}', 'barva pozadí ±{1}'],
  ['{}, {}', '{1}, {2}'],
  // catch-alls, used only when a part of them is a known text
  ['{} — {}', '{1} — {2}'], ['{}: {}', '{1}: {2}'], ['{} · {}', '{1} · {2}'], ['{} ({})', '{1} ({2})'],
];

// rich hints (text with markup): normalised text -> Czech HTML
const CS_HTML = {
  '✏ Sketch — draw a rectangle or a circle': '<b>✏ Skica</b> — nakreslete obdélník nebo kruh',
  '⬆ Extrude — give it a height': '<b>⬆ Vysunutí</b> — dejte mu výšku',
  'Sketch on a face of the part to add holes, pockets and bosses': 'Skicou na <b>ploše</b> dílu přidáte díry, kapsy a výstupky',
  'Layers are real geometry: a mask (face, rectangle, ellipse or traced image) filled solid or with a grid pattern, then embossed, engraved or cut through. Included in STL/STEP.':
    'Vrstvy jsou skutečná geometrie: <b>maska</b> (plocha, obdélník, elipsa nebo obkreslený obrázek) vyplněná plně nebo vzorem mřížky, pak <b>vytlačená</b>, <b>vyrytá</b> nebo <b>prořezaná</b>. Součást STL/STEP.',
  'Applied last, to the finished part (design and joints bend with it). Edit masks and dimensions in Flat view.':
    'Použije se nakonec, na hotový díl (design i spoje se ohnou s ním). Masky a kóty upravujte v <b>rovném pohledu</b>.',
  'Click a value in the 3D view to type it, drag it left/right to scrub, or scroll over it. Shift = ×10, Alt = ×0.1. Values accept math, e.g. 78.7/2.':
    'Klikněte na hodnotu ve 3D pohledu a napište ji, táhněte doleva/doprava nebo použijte kolečko. <kbd>Shift</kbd> = ×10, <kbd>Alt</kbd> = ×0,1. Hodnoty přijímají výpočty, např. <code>78.7/2</code>.',
  '3D models and assemblies too — it sketches, extrudes, drills, rounds and puts parts together.':
    '<b>Také 3D modely a sestavy</b> — kreslí skici, vysunuje, vrtá, zaobluje a skládá díly dohromady.',
  '“Make a 60 × 40 × 5 mm plate with four Ø4 holes 6 mm from the corners and rounded edges” · “Put the pin into the hole of the plate”.':
    '„Udělej desku 60 × 40 × 5 mm se čtyřmi dírami Ø4 6 mm od rohů a zaoblenými hranami“ · „Zasuň čep do díry v desce“.',
  'Describe what you want — Claude works on the part in the app: opens drawings, traces pictures, sets sizes, adds holes, text and objects, checks the printer and exports.':
    '<b>Popište, co chcete</b> — Claude pracuje na dílu v aplikaci: otevírá výkresy, obkresluje obrázky, nastavuje velikosti, přidává díry, text a objekty, kontroluje tiskárnu a exportuje.',
  'Made from the drawing {}: its dimensions drive the part (Dimensions tab). Below, cut or add 2D shapes on its profile and add 3D objects — holes, posts, bars, text, offsets of the profile.':
    'Vyrobeno z výkresu <b>{1}</b>: jeho kóty řídí díl (záložka Rozměry). Níže můžete na jeho profilu vyříznout nebo přidat 2D tvary a přidat 3D objekty — díry, sloupky, tyče, text, odsazení profilu.',
  'Imported 3D file {}. It is cut into flat slices — exact for walls that are vertical between flat faces, steps for slanted / curved walls. Scale it in Dimensions (or with a dimension you add).':
    'Importovaný 3D soubor <b>{1}</b>. Je rozřezán na ploché vrstvy — přesné pro svislé stěny mezi rovnými plochami, schody pro šikmé / zakřivené stěny. Měřítko nastavíte v Rozměrech (nebo kótou, kterou přidáte).',
  'Read {} dimension(s) from the drawing; outline with {} cutout(s).': 'Z výkresu načteno <b>{1}</b> kót; obrys s <b>{2}</b> výřezy.',
  'No bends — the part is flat. Add a fold (roof ∧, gutter ∨, U or Z shapes) or roll the whole part into an arc / tube.':
    'Žádné ohyby — díl je rovný.<br>Přidejte ohyb (střecha ∧, žlab ∨, tvar U nebo Z) nebo celý díl stočte do oblouku / trubky.',
  'e.g. “Make a 90 mm cookie cutter from C:\\pics\\star.png with a hanging hole” · “Add a 5 mm hole 8 mm from the top” · “Engrave my name on the flange”.':
    'např. „Udělej 90mm vykrajovátko z C:\\pics\\star.png s dírkou na pověšení“ · „Přidej díru 5 mm, 8 mm od horního okraje“ · „Vyryj moje jméno na límec“.',
  'On this part, layers go on {}: front = its top (z {} mm), back = its bottom (z {} mm). Move another object to the top of the list in the Part tab to decorate that one.':
    'Na tomto dílu jdou vrstvy na <b>{1}</b>: <i>přední</i> = jeho horní plocha (z {2} mm), <i>zadní</i> = jeho spodní plocha (z {3} mm). Chcete-li zdobit jiný objekt, přesuňte ho v záložce Díl na začátek seznamu.',
  'On this part, layers go on {}: front = its top (z {} mm), back = its bottom (z {} mm). Use Edit as 3D objects in the Part tab to choose another object.':
    'Na tomto dílu jdou vrstvy na <b>{1}</b>: <i>přední</i> = jeho horní plocha (z {2} mm), <i>zadní</i> = jeho spodní plocha (z {3} mm). Jiný objekt zvolíte přes <i>Upravit jako 3D objekty</i> v záložce Díl.',
  'Replaces the estimated value {}.': 'Nahradí odhadnutou hodnotu <b>{1}</b>.',
  'No design layers yet. Add a grid, a shape or an image — each can be embossed, engraved or cut through.':
    'Zatím žádné vrstvy designu. Přidejte mřížku, tvar nebo obrázek —<br>každý lze vytlačit, vyrýt nebo prořezat.',
  'Runs on your own Claude Code sign-in (Claude subscription or API key) — the app only gives Claude its part tools.':
    'Běží na vašem vlastním přihlášení do Claude Code (předplatné Claude nebo API klíč) — aplikace dává Claudovi jen nástroje pro díl.',
};

// ---------------------------------------------------------------------------- engine
const norm = (s) => s.replace(/\s+/g, ' ').trim();
const compiled = CS_PATTERNS.map(([en, cs]) => {
  const re = new RegExp(`^${norm(en).replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{\}/g, '(.+?)')}$`);
  const parts = norm(en).split('{}').map((s) => s.trim()).filter((s) => s.length > 2);
  return { re, cs, parts, loose: !/[A-Za-z]/.test(en), fixed: en.replace(/\{\}/g, '').length };
}).sort((a, b) => b.fixed - a.fixed); // the most specific pattern first ("Cutout {} width" before "Cutout {}")

// a value never cuts through brackets ("x (a), y (b)" splits at the comma, not at the first bracket)
function balanced(v) {
  let depth = 0;
  for (const ch of v) {
    if (ch === '(') depth++;
    else if (ch === ')' && --depth < 0) return false;
  }
  return depth === 0;
}

function byPattern(k, accept) {
  for (const { re, cs, parts, loose } of compiled) {
    const m = k.match(re);
    // a value holding the pattern's own words means two texts were joined ("background (2 colours), background (3 colours)")
    if (!m || !accept(m) || m.slice(1).some((v) => !balanced(v) || parts.some((p) => v.includes(p)))) continue;
    let changed = false;
    const out = cs.replace(/\{(\d)\}/g, (_, i) => { const v = m[+i], tr = value(v); changed ||= tr !== v; return tr; });
    if (loose && !changed) continue; // a catch-all pattern only when something in it is known
    return out;
  }
  return null;
}

/** The text in the current language (a value inside a pattern is translated too when it is a known text). */
export function t(text) {
  if (lang === 'en' || !text) return text;
  if (text.trim().includes('\n')) { // a tooltip of several lines: line by line
    const lines = text.split('\n'), tr = lines.map(t);
    if (tr.some((l, i) => l !== lines[i])) return tr.join('\n');
  }
  const k = norm(text);
  if (!k) return text;
  const lead = text.match(/^\s*/)[0], trail = text.match(/\s*$/)[0];
  if (CS[k] !== undefined) return lead + CS[k] + trail;
  // values do not span a " — " (that joins two texts) unless nothing else fits
  const out = byPattern(k, (m) => !m.slice(1).some((v) => v.includes(' — ')));
  if (out !== null) return lead + out + trail;
  if (k.includes(' — ')) {
    const parts = k.split(' — '), tr = parts.map(t);
    if (tr.some((p, i) => p !== parts[i])) return lead + tr.join(' — ') + trail;
  }
  const any = byPattern(k, () => true);
  return any !== null ? lead + any + trail : text;
}

// a value inside a pattern: a known text (also lower-case, e.g. "profile"), or as it is (numbers, names)
function value(v) {
  const tr = t(v);
  if (tr !== v || !v) return tr;
  const q = v.match(/^([“"„])(.*)([”"“])$/); // a quoted name: “Flange” -> „Límec“
  if (q) { const inner = value(q[2]); return inner !== q[2] ? `„${inner}“` : v; }
  const cap = CS[v[0].toUpperCase() + v.slice(1)];
  return cap !== undefined && v[0] !== v[0].toUpperCase() ? cap[0].toLowerCase() + cap.slice(1) : v;
}

export const getLang = () => lang;

// elements whose text is the user's own (or numbers) are left alone
const SKIP = '.ai-msg.user, .ai-msg.assistant, script, style, code.raw, [data-no-i18n]';
const SKIP_TEXT = `${SKIP}, .dim-label`;  // values on the 3D labels (their tooltips are translated)
const ATTRS = ['title', 'placeholder'];
const RICH = '.hint, p, .empty, .intro, li';

// text with markup (<b>, <i>, <code>, <kbd>, <span>, <br>): matched on its plain text, replaced by Czech HTML
const compiledHtml = Object.entries(CS_HTML).filter(([en]) => en.includes('{}')).map(([en, cs]) =>
  [new RegExp(`^${en.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{\}/g, '(.+?)')}$`), cs]);

function translateHtml(el) {
  if (el.__csHtml !== undefined && el.innerHTML === el.__csHtml) return; // already ours
  let key = '';
  for (const c of el.childNodes) {
    if (c.nodeType === 3) key += c.nodeValue;
    else if (c.nodeName === 'BR') key += ' ';
    else if (/^(B|I|EM|CODE|KBD|SPAN)$/.test(c.nodeName) && !c.children.length) key += c.textContent;
    else return;
  }
  key = norm(key);
  const esc = (v) => v.replace(/[&<>"]/g, (ch) => `&#${ch.charCodeAt(0)};`);
  let cs = CS_HTML[key];
  if (cs === undefined) {
    for (const [re, html] of compiledHtml) {
      const m = key.match(re);
      if (m) { cs = html.replace(/\{(\d)\}/g, (_, i) => esc(value(m[+i]))); break; }
    }
  }
  if (cs === undefined) return;
  el.__enHtml = el.innerHTML;
  el.innerHTML = cs;
  el.__csHtml = el.innerHTML;
}

function translateNode(node) {
  if (node.nodeType === 3) {
    const p = node.parentElement;
    if (!p || p.closest(SKIP_TEXT)) return;
    if (p.isContentEditable && p.contains(document.activeElement)) return; // the user is typing there
    const cur = node.nodeValue;
    if (node.__cs !== undefined && cur === node.__cs) return; // already ours
    const tr = t(cur);
    if (tr !== cur) { node.__en = cur; node.__cs = tr; node.nodeValue = tr; }
    return;
  }
  if (node.nodeType !== 1 || node.closest?.(SKIP)) return;
  if (node.matches?.(RICH)) translateHtml(node);
  for (const a of ATTRS) {
    const v = node.getAttribute?.(a);
    if (v && v !== node[`__cs_${a}`]) {
      const tr = t(v);
      if (tr !== v) { node[`__en_${a}`] = v; node[`__cs_${a}`] = tr; node.setAttribute(a, tr); }
    }
  }
  for (const el of node.querySelectorAll?.(RICH) || []) if (!el.closest(SKIP)) translateHtml(el);
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n = walker.nextNode();
  while (n) {
    if (n.nodeType === 3) translateNode(n);
    else for (const a of ATTRS) if (n.hasAttribute(a)) translateNode_attr(n, a);
    n = walker.nextNode();
  }
}

function translateNode_attr(el, a) {
  if (el.closest(SKIP)) return;
  const v = el.getAttribute(a);
  if (!v || v === el[`__cs_${a}`]) return;
  const tr = t(v);
  if (tr !== v) { el[`__en_${a}`] = v; el[`__cs_${a}`] = tr; el.setAttribute(a, tr); }
}

/** Back to the English originals (switching languages live). */
function restore(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n = walker.currentNode;
  while (n) {
    if (n.nodeType === 3 && n.__en !== undefined && n.nodeValue === n.__cs) { n.nodeValue = n.__en; delete n.__en; delete n.__cs; }
    if (n.nodeType === 1) {
      if (n.__enHtml !== undefined && n.innerHTML === n.__csHtml) { n.innerHTML = n.__enHtml; delete n.__enHtml; delete n.__csHtml; }
      for (const a of ATTRS) if (n[`__en_${a}`] !== undefined && n.getAttribute(a) === n[`__cs_${a}`]) { n.setAttribute(a, n[`__en_${a}`]); delete n[`__en_${a}`]; delete n[`__cs_${a}`]; }
    }
    n = walker.nextNode();
  }
}

let observer = null;
export function initI18n() {
  document.documentElement.lang = lang;
  for (const f of ['confirm', 'alert']) { const orig = window[f].bind(window); window[f] = (msg) => orig(t(String(msg ?? ''))); }
  if (lang !== 'en') translateNode(document.body);
  observer = new MutationObserver((muts) => {
    if (lang === 'en') return;
    for (const m of muts) {
      if (m.type === 'childList') {
        if (m.target.matches?.(RICH) && !m.target.closest(SKIP)) translateHtml(m.target); // its content was replaced
        m.addedNodes.forEach(translateNode);
      }
      else if (m.type === 'characterData') translateNode(m.target);
      else if (m.type === 'attributes') translateNode_attr(m.target, m.attributeName);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  const btn = document.getElementById('langBtn');
  if (btn) {
    const show = () => { btn.textContent = lang === 'cs' ? 'EN' : 'CZ'; btn.title = lang === 'cs' ? 'Switch to English' : 'Přepnout do češtiny'; };
    show();
    btn.addEventListener('click', () => { setLang(lang === 'cs' ? 'en' : 'cs'); show(); });
  }
}

export function setLang(l) {
  if (l === lang) return;
  lang = l;
  try { localStorage.setItem(KEY, l); } catch { /* ignore */ }
  document.documentElement.lang = l;
  if (l === 'en') restore(document.body);
  else translateNode(document.body);
}
