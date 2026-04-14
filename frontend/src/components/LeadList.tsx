import type { Lead } from "../api/client";

type Props = {
  leads: Lead[];
  onSave: (lead: Lead) => void;
  onSelect: (lead: Lead) => void;
};

export function LeadList({ leads, onSave, onSelect }: Props) {
  return (
    <section className="panel">
      <h2>Leads</h2>
      <ul className="lead-list">
        {leads.map((lead) => (
          <li key={lead.business_id} className="lead-card" onClick={() => onSelect(lead)}>
            <div className="lead-top">
              <strong>{lead.name}</strong>
              <span className="score">{lead.final_score}</span>
            </div>
            <div>{lead.insurance_class ?? "Unknown"}</div>
            <div>{Math.round(lead.distance_from_route_m)}m from route</div>
            <small>{lead.explanation.fit}</small>
            <small>{lead.explanation.distance}</small>
            <small>{lead.explanation.actionability}</small>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSave(lead);
              }}
            >
              Save
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
