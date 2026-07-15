import io
from PIL import Image, ImageDraw, ImageOps




def get_img_bytes_optimized(pil_img, max_width=1000):

    # Ridimensiona mantenendo il rapporto d'aspetto
    w_percent       = (max_width / float(pil_img.size[0]))
    h_size          = int((float(pil_img.size[1]) * float(w_percent)))
    pil_img         = pil_img.resize((max_width, h_size), Image.Resampling.LANCZOS)
    img_byte_arr    = io.BytesIO()

    pil_img.save(img_byte_arr, format='JPEG', quality=60) 

    return img_byte_arr.getvalue()



def disegna_punti_critici(image_bytes, lista_punti, abilita_marker=True):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.exif_transpose(img)

    # Se i marker sono disabilitati salta la funzione
    if not abilita_marker:
        return img
    
    else:
        draw = ImageDraw.Draw(img)
        width, height = img.size
        #colori = ["red", "blue", "yellow", "cyan", "magenta", "lime", "orange", "purple"]
        colore = "red"
        
        for i, punto in enumerate(lista_punti):
            #colore = colori[i % len(colori)]
            coord = punto.get('coordinate', {'x': 50, 'y': 50})
            x_raw = coord.get('x')
            y_raw = coord.get('y')

            # --- FIX: Se x o y sono None, salta questo punto ---
            if x_raw is None or y_raw is None:
                continue

            size = 80
            
            # --- CORREZIONE: Normalizzazione dinamica ---
            x_raw = coord.get('x', 40)
            y_raw = coord.get('y', 50)
            x = (x_raw / 1000) * width if x_raw > 100 else (x_raw / 100) * width
            y = (y_raw / 1000) * height if y_raw > 100 else (y_raw / 100) * height
            
            # Disegna cerchio e testo
            draw.ellipse([x-size, y-size, x+size, y+size], outline=colore, width=8)
            draw.text((x, y), str(i + 1), fill=colore, font_size=70, anchor="mm")
            
        return img