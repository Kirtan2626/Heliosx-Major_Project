from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.database import Base
from datetime import datetime
import uuid

class Site(Base):
    __tablename__ = "sites"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timezone_offset = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    simulations = relationship("SimulationRun", back_populates="site")

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id = Column(String, ForeignKey("sites.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Inputs
    weather_data = Column(JSON)
    
    # Aggregated Results
    total_fixed_wh = Column(Float)
    total_tracker_wh = Column(Float)
    total_ai_wh = Column(Float)
    
    # Financial
    kwh_loss = Column(Float)
    financial_loss_usd = Column(Float)
    maintenance_urgency = Column(String)
    
    # Relationships
    site = relationship("Site", back_populates="simulations")
    faults = relationship("FaultLog", back_populates="simulation")

class FaultLog(Base):
    __tablename__ = "fault_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String, ForeignKey("simulation_runs.id"))
    fault_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(String)
    detected_at = Column(DateTime, default=datetime.utcnow)

    simulation = relationship("SimulationRun", back_populates="faults")
