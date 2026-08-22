import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — CURV AI",
  description: "Privacy policy for CURV AI marketing platform.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="max-w-2xl mx-auto px-6 py-16">
        <h1 className="font-display text-3xl font-bold mb-2">Privacy Policy</h1>
        <p className="text-sm text-text-muted mb-8">Last updated: July 28, 2026</p>

        <div className="prose prose-invert max-w-none space-y-6 text-sm text-text-secondary leading-relaxed">
          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">1. Information We Collect</h2>
            <p><strong className="text-text">Account information:</strong> name, email, password (hashed).</p>
            <p><strong className="text-text">Business information:</strong> brand details, industry, goals, audience data you provide.</p>
            <p><strong className="text-text">Usage data:</strong> campaign performance metrics, content interactions, platform analytics.</p>
            <p><strong className="text-text">OAuth tokens:</strong> for connected channels (Google, Meta, etc.) — stored encrypted, never logged.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">2. How We Use Your Information</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>To provide and improve the CURV AI service</li>
              <li>To generate AI-powered marketing campaigns and content</li>
              <li>To analyse and report on campaign performance</li>
              <li>To send service notifications and updates</li>
              <li>To prevent abuse and ensure platform security</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">3. Data Storage and Security</h2>
            <p>All data is stored in encrypted PostgreSQL databases with Row-Level Security (RLS). Every tenant&rsquo;s data is isolated. OAuth tokens are encrypted at rest. All mutations are audit-logged. We use TLS 1.3 for data in transit.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">4. Data Sharing</h2>
            <p>We do not sell your data. We share data only with:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>AI providers (Anthropic, OpenAI) for content generation — minimal context only</li>
              <li>Connected platforms (Google, Meta, etc.) when you publish content</li>
              <li>Payment processors (Stripe, Razorpay) for billing — we never see card details</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">5. AI Processing</h2>
            <p>When generating campaigns, we send your business context to AI providers. We minimise the data sent and never send sensitive customer data (PII) to AI models. AI providers are contractually prohibited from using your data for training.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">6. Your Rights</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong className="text-text">Access:</strong> request a copy of your data</li>
              <li><strong className="text-text">Deletion:</strong> request permanent deletion of your data</li>
              <li><strong className="text-text">Export:</strong> download your data in JSON/CSV format</li>
              <li><strong className="text-text">Opt-out:</strong> unsubscribe from non-essential communications</li>
            </ul>
            <p>To exercise these rights, contact <a href="mailto:privacy@curv.ai" className="text-accent hover:underline">privacy@curv.ai</a>.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">7. Data Retention</h2>
            <p>Active account data is retained while your account is active. Deleted accounts have data purged within 30 days. Audit logs are retained for 90 days for security purposes.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">8. Cookies</h2>
            <p>We use essential cookies for authentication and session management. We do not use third-party advertising cookies. Analytics cookies (if enabled) are opt-in.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">9. Compliance</h2>
            <p>We comply with GDPR, CCPA, and DPDP Act (India) requirements. For data protection inquiries, contact <a href="mailto:dpo@curv.ai" className="text-accent hover:underline">dpo@curv.ai</a>.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">10. Contact</h2>
            <p>For privacy questions, contact <a href="mailto:privacy@curv.ai" className="text-accent hover:underline">privacy@curv.ai</a>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
