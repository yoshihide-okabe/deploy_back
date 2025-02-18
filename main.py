from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os

# .env ファイルの読み込み
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") # 環境変数から DATABASE_URL を取得

print(f"✅ DATABASE_URL: {DATABASE_URL}")  # デバッグ用

# SQLAlchemy の設定
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 商品マスターのモデル
class Product(Base):
    __tablename__ = "m_product_okabe"

    PRD_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)  # 商品識別ID
    CODE = Column(String(13), unique=True, index=True, nullable=False)  # 商品コード
    NAME = Column(String(50), nullable=False)  # 商品名称
    PRICE = Column(Integer, nullable=False)  # 商品単価

app = FastAPI()

# CORSの設定を追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.jsのURLを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可 (GET, POST, PUT, DELETEなど)
    allow_headers=["*"],  # すべてのヘッダーを許可
)

print(app.routes)

# DBセッションを取得する依存関係
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

# ルートのエンドポイント
@app.get("/")
async def root():
    return {"message": "Hello, World!"}

# 商品コードを受け取って商品情報を返すAPI
@app.get("/product/{code}")
def get_product(code: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.CODE == code).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    
    return {"product_name": product.NAME, "product_price": product.PRICE}

