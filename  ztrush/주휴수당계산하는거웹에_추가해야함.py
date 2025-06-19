from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="주휴수당 계산기 API", description="2025년 기준 주휴수당 자동 계산기", version="1.0.0")

class CalcResult(BaseModel):
    weekly_hours: float = Field(..., description="주간 총 소정근로시간")
    eligible: bool = Field(..., description="주휴수당 지급 대상 여부 (주 15시간 미만 근로자는 False)")
    payable_hours: float = Field(..., description="주휴수당 산정에 사용된 유급휴일 시간")
    주휴수당: int = Field(..., description="지급해야 할 주휴수당 (원)")


def calc_주휴수당(hourly_wage: float, daily_hours: float, weekly_days: int) -> CalcResult:
    """2025년 기준 주휴수당 계산 공식
    주휴수당 = (주 소정근로시간 / 40) * 8 * 시급
    단, 주 소정근로시간이 15h 미만이면 지급 대상 아님
    """
    weekly_hours = daily_hours * weekly_days
    eligible = weekly_hours >= 15

    if not eligible:
        return CalcResult(
            weekly_hours=weekly_hours,
            eligible=False,
            payable_hours=0.0,
            주휴수당=0,
        )

    payable_hours = (weekly_hours / 40) * 8  # 비례 산정
    payable_amount = int(payable_hours * hourly_wage)

    return CalcResult(
        weekly_hours=weekly_hours,
        eligible=True,
        payable_hours=round(payable_hours, 2),
        주휴수당=payable_amount,
    )


@app.get("/calc", response_model=CalcResult, summary="주휴수당 계산")
async def calc_endpoint(
    hourly_wage: float = Query(..., gt=0, description="시급 (원)"),
    daily_hours: float = Query(..., gt=0, description="1일 소정근로시간"),
    weekly_days: int = Query(..., gt=0, le=7, description="주 소정근로일 수"),
):
    """쿼리 파라미터로 시급, 1일 근로시간, 주 근로일 수를 받아 주휴수당을 JSON 으로 반환합니다."""
    try:
        return calc_주휴수당(hourly_wage, daily_hours, weekly_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root_page():
    """간단한 데모 페이지 (HTML + JS)"""
    return (
        """
        <!DOCTYPE html>
        <html lang=\"ko\">
        <head>
            <meta charset=\"UTF-8\" />
            <title>주휴수당 계산기</title>
            <style>
                body {font-family: Arial, sans-serif; margin: 40px;}
                label {display: block; margin-top: 10px;}
                input {padding: 6px; width: 160px;}
                button {margin-top: 20px; padding: 8px 16px;}
                #result {margin-top: 30px; font-weight: bold; font-size: 1.2rem;}
            </style>
        </head>
        <body>
            <h1>주휴수당 계산기 (2025)</h1>
            <form id=\"calcForm\" onsubmit=\"return false;\">
                <label>시급(원): <input type=\"number\" id=\"hourly\" required /></label>
                <label>1일 근로시간: <input type=\"number\" step=\"0.1\" id=\"daily\" required /></label>
                <label>주 근로일 수: <input type=\"number\" id=\"days\" required /></label>
                <button onclick=\"calculate()\">계산하기</button>
            </form>
            <div id=\"result\"></div>

            <script>
                function calculate() {
                    const hourly = document.getElementById('hourly').value;
                    const daily = document.getElementById('daily').value;
                    const days = document.getElementById('days').value;
                    fetch(`/calc?hourly_wage=${hourly}&daily_hours=${daily}&weekly_days=${days}`)
                        .then(resp => resp.json())
                        .then(data => {
                            if (!data.eligible) {
                                document.getElementById('result').innerText = `주 ${data.weekly_hours}시간 근로 → 주휴수당 대상 아님 (15시간 미만)`;
                            } else {
                                document.getElementById('result').innerText = `주휴수당: ${data.주휴수당.toLocaleString()}원 (유급 ${data.payable_hours}h)`;
                            }
                        })
                        .catch(err => {
                            document.getElementById('result').innerText = '계산 오류: ' + err;
                        });
                }
            </script>
        </body>
        </html>
        """
    )

# === 로컬 실행 방법 ===
# 1) fastapi, uvicorn 설치: pip install fastapi uvicorn[standard]
# 2) 실행: uvicorn main:app --reload --port 8000
# 3) 브라우저에서 http://localhost:8000 열기
