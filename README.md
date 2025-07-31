git clone https://github.com/OgboiEhioma/university-complaint-system.git
cd university-complaint-system

BACKEND SETUP
cd backend

pip install -r requirements.txt

complaint_env\Scripts\activate

alembic init alembic

alembic revision --autogenerate -m "Initial migration"

alembic upgrade head

complaint_env\Scripts\activate

python main.py
