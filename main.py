from fastapi import FastAPI
# from fastapi.responses import Response

app = FastAPI()

@app.get('/health')
async def health():
  return { 'success': True, 'message': 'The app is working fine' }