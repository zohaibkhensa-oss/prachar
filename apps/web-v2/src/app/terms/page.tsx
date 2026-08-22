import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service — CURV AI",
  description: "Terms of service for CURV AI marketing platform.",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="max-w-2xl mx-auto px-6 py-16">
        <h1 className="font-display text-3xl font-bold mb-2">Terms of Service</h1>
        <p className="text-sm text-text-muted mb-8">Last updated: July 28, 2026</p>

        <div className="prose prose-invert max-w-none space-y-6 text-sm text-text-secondary leading-relaxed">
          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">1. Acceptance of Terms</h2>
            <p>By accessing or using CURV AI (&ldquo;the Service&rdquo;), you agree to be bound by these Terms of Service. If you do not agree, please do not use the Service.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">2. Description of Service</h2>
            <p>CURV AI is an AI-driven marketing platform that provides campaign planning, content generation, performance analytics, and multi-channel publishing for businesses.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">3. User Accounts</h2>
            <p>You are responsible for maintaining the security of your account and password. You must be at least 18 years old to use this Service. You are responsible for all content posted through your account.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">4. Acceptable Use</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>No engagement-bait, fake reviews, or follower buying</li>
              <li>No medical, financial, or &ldquo;guaranteed results&rdquo; claims</li>
              <li>No scraping behind authentication walls</li>
              <li>No spam or unsolicited communications</li>
              <li>Comply with all applicable advertising regulations</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">5. AI-Generated Content</h2>
            <p>CURV AI uses AI to generate marketing content. You are responsible for reviewing and approving all content before publication. We do not guarantee specific results or performance outcomes.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">6. Subscriptions and Billing</h2>
            <p>Paid subscriptions are billed in advance on a recurring basis. You can cancel at any time. Refunds are subject to our refund policy. Plan limits (token usage, brand count, channels) are enforced per plan tier.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">7. Intellectual Property</h2>
            <p>You retain ownership of content you upload. AI-generated content is licensed to you for commercial use. CURV AI retains ownership of the platform, algorithms, and underlying technology.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">8. Limitation of Liability</h2>
            <p>CURV AI is provided &ldquo;as is&rdquo; without warranties of any kind. We are not liable for indirect, incidental, or consequential damages arising from use of the Service.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">9. Termination</h2>
            <p>We may terminate or suspend accounts that violate these Terms. You may cancel your account at any time through the settings page.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-text mb-2">10. Contact</h2>
            <p>For questions about these Terms, contact us at <a href="mailto:support@curv.ai" className="text-accent hover:underline">support@curv.ai</a>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
