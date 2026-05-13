import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface Props {
  data: any[];
  currentIndex: number;
}

export default function AnalyticsCharts({ data, currentIndex }: Props) {
  if (!data || data.length === 0) return <div className="h-48 flex items-center justify-center text-slate-500">No telemetry data</div>;
  
  const currentDataPoint = data[currentIndex];
  
  return (
    <div className="w-full h-48" style={{ minHeight: '192px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <XAxis dataKey="time" stroke="#64748b" fontSize={10} tickFormatter={(val, i) => i % 6 === 0 ? val : ''} />
          <YAxis stroke="#64748b" fontSize={10} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
            itemStyle={{ color: '#f8fafc' }}
          />
          {currentDataPoint && (
              <ReferenceLine x={currentDataPoint.time} stroke="#f97316" strokeDasharray="3 3" />
          )}
          <Line type="monotone" dataKey="energy_ai" name="AI Yield" stroke="#f97316" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="energy_tracker" name="Perfect Tracker" stroke="#3b82f6" strokeWidth={1} dot={false} strokeDasharray="5 5" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
