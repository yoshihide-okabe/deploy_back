from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.types import DateTime
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
import os

# .env ファイルの読み込み
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") # 環境変数から DATABASE_URL を取得

print(f"✅ DATABASE_URL: {DATABASE_URL}")  # デバッグ用

# SQLAlchemyの設定（utf8mb4を設定しない）
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI インスタンス作成
app = FastAPI()


# CORSの設定を追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://tech0-gen8-step4-pos-app-115.azurewebsites.net"],  # Next.jsのURLを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可 (GET, POST, PUT, DELETEなど)
    allow_headers=["*"],  # すべてのヘッダーを許可
)

# DBモデル定義（商品マスター）
class Product(Base):
    __tablename__ = "m_product_okabe"

    PRD_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)  # 商品識別ID
    CODE = Column(String(13), unique=True, index=True, nullable=False)  # 商品コード
    NAME = Column(String(50), nullable=False)  # 商品名称
    PRICE = Column(Integer, nullable=False)  # 商品単価

# DBモデル定義（取引）
class Transaction(Base):
    __tablename__ = "transactions_okabe"

    TRD_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    DATETIME = Column(DateTime, nullable=False, server_default=func.now())
    EMP_CD = Column(String, nullable=False)
    STORE_CD = Column(String, nullable=False)
    POS_NO = Column(String, nullable=False)
    TOTAL_AMT = Column(Integer, nullable=False)

# DBモデル定義（取引明細）
class TransactionDetail(Base):
    __tablename__ = "transaction_details_okabe"

    DTL_ID = Column(Integer, primary_key=True, index=True)
    TRD_ID = Column(Integer, ForeignKey("transactions_okabe.TRD_ID"), nullable=False)
    PRD_ID = Column(Integer, ForeignKey("m_product_okabe.PRD_ID"), nullable=False)
    PRD_CODE = Column(String(13), nullable=False)
    PRD_NAME = Column(String(50), nullable=False)
    PRD_PRICE = Column(Integer, nullable=False)

# Pydantic モデル定義
class PurchaseItem(BaseModel):
    code: str
    prd_name: str
    price: int

class PurchaseRequest(BaseModel):
    emp_cd: str
    store_cd: str
    pos_no: str
    items: List[PurchaseItem]

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

# 商品コードの読み込みボタンのAPI
@app.get("/product/{code}")
def get_product(code: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.CODE == code).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    return {"CODE": product.CODE, "NAME": product.NAME, "PRICE": product.PRICE}

# 購入ボタンのAPI
@app.post("/purchase")
def purchase_items(request: PurchaseRequest, db: Session = Depends(get_db)):
    try:
        emp_cd = request.emp_cd.strip() if request.emp_cd.strip() else '9999999999'
        
        # 新規取引の登録
        new_transaction = Transaction(
            EMP_CD=emp_cd,
            STORE_CD=request.store_cd,
            POS_NO=request.pos_no,
            TOTAL_AMT=0
        )
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        transaction_id = new_transaction.TRD_ID
        
        total_amount = 0

        # 現在の最大 DTL_ID を取得（並行処理の競合を防ぐ）
        max_dtl_id = db.query(func.coalesce(func.max(TransactionDetail.DTL_ID), 0)).scalar() or 0

        new_details = []  # バルクインサートのためにリストを作成
        
        for item in request.items:
            product = db.query(Product).filter(Product.CODE == item.code).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"商品コード {item.code} が見つかりません")

            # DTL_ID を手動で増やして設定
            max_dtl_id += 1

            # 取引明細の登録
            new_detail = TransactionDetail(
                DTL_ID=max_dtl_id,  # 取引ごとの連番
                TRD_ID=transaction_id,
                PRD_ID=product.PRD_ID,
                PRD_CODE=product.CODE,
                PRD_NAME=product.NAME,
                PRD_PRICE=product.PRICE
            )
            new_details.append(new_detail)  # 一括登録のためにリストに追加
            total_amount += product.PRICE
        
        # `flush()` を使ってデータを即時反映
        for detail in new_details:
            db.add(detail)
        db.flush()

        # 取引の合計金額を更新
        db.query(Transaction).filter(Transaction.TRD_ID == transaction_id).update({"TOTAL_AMT": total_amount})
        db.commit()

        return {"success": True, "total_amount": total_amount}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"サーバーエラー: {str(e)}")

    finally:
        db.close()

# FastAPI 実行
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
