#!/usr/bin/env python3
"""등록된 라우트 확인 스크립트"""

from app.main import app

def check_routes():
    print("🔍 등록된 라우트 목록:")
    print("-" * 50)
    
    route_count = 0
    order_routes = []
    
    for route in app.routes:
        route_count += 1
        methods = getattr(route, 'methods', ['N/A'])
        path = getattr(route, 'path', 'N/A')
        
        print(f"{methods} {path}")
        
        # order 관련 라우트 별도 수집
        if '/order' in path:
            order_routes.append(f"{methods} {path}")
    
    print("-" * 50)
    print(f"총 {route_count}개 라우트 등록됨")
    
    if order_routes:
        print(f"\n📋 Order 관련 라우트 ({len(order_routes)}개):")
        for route in order_routes:
            print(f"  {route}")
    else:
        print("\n❌ Order 관련 라우트가 없습니다!")
    
    # 특정 라우트 확인
    target_route = "/order/test-report/{order_id}"
    found = any(target_route.replace('{order_id}', '') in str(route.path) for route in app.routes)
    print(f"\n🎯 찾는 라우트 '/order/test-report/{{order_id}}': {'✅ 발견됨' if found else '❌ 없음'}")

if __name__ == "__main__":
    check_routes()