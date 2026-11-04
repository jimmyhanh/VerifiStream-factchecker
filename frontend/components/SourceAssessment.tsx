import { sourceAssessment, type SourceMetadata } from "@/lib/source-assessment";
export default function SourceAssessment({
  source,
}: {
  source: SourceMetadata;
}) {
  const assessment = sourceAssessment(source);
  return (
    <details className="source-assessment">
      <summary>Source trust assessment: {assessment.rating}</summary>
      <p>{assessment.reason}</p>
      <dl>
        {assessment.signals.map((s) => (
          <div key={s.label}>
            <dt>{s.label}</dt>
            <dd>{s.value}</dd>
          </div>
        ))}
      </dl>
      <p className="small">
        Publisher and date metadata may be page-declared and unverified. A
        primary source, recent date, agreement, or professional-looking website
        alone does not establish trust. Political bias is not scored. This
        assessment does not change Evidence Confidence.
      </p>
      <span className="small">
        {assessment.version} · Numeric trust score withheld
      </span>
    </details>
  );
}
