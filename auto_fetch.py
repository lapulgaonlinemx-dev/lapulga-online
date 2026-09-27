import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# Configuración del enlace de afiliado
AFFILIATE_LINK = "https://www.mercadolibre.com.mx/social/eg20260925105329727"

def init_firebase():
    """Inicializa la conexión a Firebase usando archivo local o Variable de Entorno"""
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    elif "FIREBASE_CREDENTIALS" in os.environ:
        cred_dict = json.loads(os.environ["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
    else:
        raise Exception("No se encontraron las credenciales de Firebase.")
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

def fetch_ml_deals():
    """Obtiene ofertas de Mercado Libre México"""
    # Consulta a la API de búsqueda de Mercado Libre México (MLM)
    url = "https://api.mercadolibre.com/sites/MLM/search?q=oferta&limit=15"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error al consultar Mercado Libre API: {response.status_code}")
        return []
    
    results = response.json().get("results", [])
    deals = []

    for item in results:
        price = item.get("price", 0)
        original_price = item.get("original_price") or (price * 1.25) # Estimación si no hay precio previo
        
        # Filtrar solo productos con descuento real
        if original_price > price:
            thumbnail = item.get("thumbnail", "").replace("I.jpg", "O.jpg") # Imagen de alta resolución
            
            # Mapeo de categorías básico
            cat_id = item.get("category_id", "")
            category = "Tech"
            if "MLM1430" in cat_id or "MLM1144" in cat_id:
                category = "Gaming"
            elif "MLM1430" in cat_id:
                category = "Moda"

            deals.append({
                "title": item.get("title", "Oferta Destacada"),
                "store": "Mercado Libre",
                "category": category,
                "price": float(price),
                "oldPrice": float(original_price),
                "image": thumbnail,
                "link": AFFILIATE_LINK, # Enlace de afiliado
                "active": True,
                "ml_id": item.get("id")
            })
    return deals

def sync_to_firestore(db, deals):
    """Limpia las ofertas viejas e inserta las nuevas en Firebase"""
    products_ref = db.collection("products")
    
    # 1. Eliminar ofertas antiguas para mantener la lista fresca
    docs = products_ref.stream()
    for doc in docs:
        doc.reference.delete()
    print("🧹 Ofertas anteriores limpiadas de la base de datos.")

    # 2. Agregar nuevas ofertas
    for deal in deals:
        products_ref.add(deal)
        print(f"✅ Agregado: {deal['title']} - ${deal['price']} MXN")

if __name__ == "__main__":
    db = init_firebase()
    print("🔎 Buscando ofertas en Mercado Libre...")
    new_deals = fetch_ml_deals()
    if new_deals:
        print(f"🔥 Se encontraron {len(new_deals)} ofertas. Sincronizando...")
        sync_to_firestore(db, new_deals)
        print("🚀 Sincronización completada con éxito.")
    else:
        print("No se encontraron ofertas relevantes en este ciclo.")