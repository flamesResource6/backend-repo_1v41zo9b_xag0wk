import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

# Database helpers
from database import db, create_document, get_documents

app = FastAPI(title="Perfume 3D Shop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Utils ----------

def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    d = {**doc}
    _id = d.get("_id")
    if isinstance(_id, ObjectId):
        d["id"] = str(_id)
        del d["_id"]
    return d

# ---------- Schemas ----------

class ProductIn(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in USD")
    category: str = Field("perfume", description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
    image: Optional[str] = Field(None, description="Main image URL")
    rating: Optional[float] = Field(4.5, ge=0, le=5)
    notes: Optional[List[str]] = Field(default_factory=list, description="Fragrance notes")

class ProductOut(ProductIn):
    id: str

# ---------- Routes ----------

@app.get("/", tags=["health"]) 
def read_root():
    return {"message": "Perfume 3D Shop API is running"}

@app.get("/test", tags=["health"]) 
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# Products
@app.get("/products", response_model=List[ProductOut], tags=["products"]) 
def list_products(limit: int = 50, q: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    filt = {}
    if q:
        # Simple text search on title using case-insensitive regex
        filt = {"title": {"$regex": q, "$options": "i"}}
    docs = get_documents("product", filt, min(limit, 100))
    return [serialize_doc(d) for d in docs]

@app.post("/products", response_model=str, tags=["products"]) 
def create_product(product: ProductIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    new_id = create_document("product", product.model_dump())
    return new_id

@app.get("/products/{product_id}", response_model=ProductOut, tags=["products"]) 
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = db["product"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_doc(doc)

@app.post("/seed", tags=["dev"]) 
def seed_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    existing = db["product"].count_documents({})
    if existing > 0:
        return {"status": "ok", "message": "Products already exist", "count": existing}
    samples = [
        {
            "title": "Citrus Bloom Eau de Parfum",
            "description": "A bright, sparkling blend of bergamot, neroli, and white musk.",
            "price": 68.0,
            "category": "perfume",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1541643600914-78b084683601?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.7,
            "notes": ["bergamot", "neroli", "white musk"]
        },
        {
            "title": "Amber Leaf Elixir",
            "description": "Warm amber wrapped in vanilla and a hint of tobacco leaf.",
            "price": 84.0,
            "category": "perfume",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1595433707802-6b2626ef1c86?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.6,
            "notes": ["amber", "vanilla", "tobacco"]
        },
        {
            "title": "Verdant Whisper",
            "description": "Green tea freshness meets jasmine petals and cedarwood.",
            "price": 72.0,
            "category": "perfume",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1563170423-18f482d82cc8?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.5,
            "notes": ["green tea", "jasmine", "cedarwood"]
        },
    ]
    for s in samples:
        create_document("product", s)
    count = db["product"].count_documents({})
    return {"status": "ok", "inserted": len(samples), "count": count}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
