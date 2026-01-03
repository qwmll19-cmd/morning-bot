"""로또 데이터 DB 관리 (SQLAlchemy)"""
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, date
from backend.app.db.models import LottoDraw

class LottoDBManager:
    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy Session
        """
        self.db = db
    
    def save_draw(self, draw_info: Dict) -> bool:
        """
        회차 데이터 저장 (중복 방지)
        
        Returns:
            bool: 새로 저장되었으면 True, 중복이면 False
        """
        try:
            # 이미 존재하는지 확인
            existing = self.db.query(LottoDraw).filter(
                LottoDraw.draw_no == draw_info['draw_no']
            ).first()
            
            if existing:
                return False
            
            # 날짜 문자열을 date 객체로 변환
            draw_date_str = draw_info['date']
            if isinstance(draw_date_str, str):
                draw_date = datetime.strptime(draw_date_str, '%Y-%m-%d').date()
            else:
                draw_date = draw_date_str
            
            # 새로 저장
            draw = LottoDraw(
                draw_no=draw_info['draw_no'],
                draw_date=draw_date,
                n1=draw_info['n1'],
                n2=draw_info['n2'],
                n3=draw_info['n3'],
                n4=draw_info['n4'],
                n5=draw_info['n5'],
                n6=draw_info['n6'],
                bonus=draw_info['bonus']
            )
            self.db.add(draw)
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"❌ DB 저장 실패 (회차 {draw_info['draw_no']}): {e}")
            self.db.rollback()
            return False
    
    def get_max_draw_no(self) -> Optional[int]:
        """DB에 저장된 최대 회차 번호"""
        result = self.db.query(LottoDraw.draw_no).order_by(
            LottoDraw.draw_no.desc()
        ).first()
        return result[0] if result else None
    
    def get_draw_count(self) -> int:
        """총 저장된 회차 수"""
        return self.db.query(LottoDraw).count()
    
    def get_recent_draws(self, n: int = 200) -> List[Dict]:
        """
        최근 N개 회차 조회 (내림차순)
        
        Returns:
            List[Dict]: [{draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus}, ...]
        """
        draws = self.db.query(LottoDraw).order_by(
            LottoDraw.draw_no.desc()
        ).limit(n).all()
        
        return [
            {
                'draw_no': draw.draw_no,
                'draw_date': draw.draw_date,
                'n1': draw.n1,
                'n2': draw.n2,
                'n3': draw.n3,
                'n4': draw.n4,
                'n5': draw.n5,
                'n6': draw.n6,
                'bonus': draw.bonus
            }
            for draw in draws
        ]
    
    def get_draw_by_no(self, draw_no: int) -> Optional[Dict]:
        """특정 회차 조회"""
        draw = self.db.query(LottoDraw).filter(
            LottoDraw.draw_no == draw_no
        ).first()
        
        if not draw:
            return None
        
        return {
            'draw_no': draw.draw_no,
            'draw_date': draw.draw_date,
            'n1': draw.n1,
            'n2': draw.n2,
            'n3': draw.n3,
            'n4': draw.n4,
            'n5': draw.n5,
            'n6': draw.n6,
            'bonus': draw.bonus
        }
