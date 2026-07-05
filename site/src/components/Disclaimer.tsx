export default function Disclaimer({ text }: { text: string }) {
  return (
    <div className="disclaimer" role="note">
      ⚠️ {text}
    </div>
  );
}
