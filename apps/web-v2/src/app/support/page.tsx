import { Metadata } from "next";
import { Mail, MessageCircle, Book, Zap, Clock } from "lucide-react";

export const metadata: Metadata = {
  title: "Support — PRACHAR",
  description: "Get help with PRACHAR AI marketing platform.",
};

export default function SupportPage() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-display text-3xl font-bold mb-2">How can we help?</h1>
        <p className="text-sm text-text-muted mb-10">We're here to help you get the most out of PRACHAR.</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
          <a
            href="mailto:support@prachar.ai"
            className="glass rounded-xl p-5 hover:border-accent/20 transition-colors group"
          >
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center mb-3 group-hover:bg-accent/20 transition-colors">
              <Mail className="w-5 h-5 text-accent" />
            </div>
            <h3 className="font-display font-semibold text-text mb-1">Email Support</h3>
            <p className="text-xs text-text-secondary mb-2">For account, billing, and technical issues.</p>
            <p className="text-xs text-accent">support@prachar.ai</p>
          </a>

          <a
            href="https://wa.me/919999999999"
            target="_blank"
            rel="noopener noreferrer"
            className="glass rounded-xl p-5 hover:border-green-500/20 transition-colors group"
          >
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center mb-3 group-hover:bg-green-500/20 transition-colors">
              <MessageCircle className="w-5 h-5 text-green-400" />
            </div>
            <h3 className="font-display font-semibold text-text mb-1">WhatsApp Support</h3>
            <p className="text-xs text-text-secondary mb-2">Quick questions and campaign help.</p>
            <p className="text-xs text-green-400">Chat with us →</p>
          </a>

          <div className="glass rounded-xl p-5">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-3">
              <Book className="w-5 h-5 text-blue-400" />
            </div>
            <h3 className="font-display font-semibold text-text mb-1">Documentation</h3>
            <p className="text-xs text-text-secondary mb-2">Guides, tutorials, and best practices.</p>
            <p className="text-xs text-blue-400">Coming soon</p>
          </div>

          <div className="glass rounded-xl p-5">
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center mb-3">
              <Zap className="w-5 h-5 text-accent" />
            </div>
            <h3 className="font-display font-semibold text-text mb-1">Feature Requests</h3>
            <p className="text-xs text-text-secondary mb-2">Suggest new features or improvements.</p>
            <p className="text-xs text-accent">features@prachar.ai</p>
          </div>
        </div>

        <div className="glass rounded-xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-text-muted" />
            <h3 className="font-display font-semibold text-text">Response Times</h3>
          </div>
          <div className="space-y-2 text-xs text-text-secondary">
            <div className="flex items-center justify-between">
              <span>Email (Starter plan)</span>
              <span className="text-text-muted">Within 48 hours</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Email (Growth plan)</span>
              <span className="text-text-muted">Within 24 hours</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Email + WhatsApp (Agency plan)</span>
              <span className="text-text-muted">Within 4 hours</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Critical bugs</span>
              <span className="text-green-400">Same day</span>
            </div>
          </div>
        </div>

        <div className="glass rounded-xl p-5">
          <h3 className="font-display font-semibold text-text mb-3">Frequently Asked Questions</h3>
          <div className="space-y-4 text-xs">
            <div>
              <p className="font-medium text-text mb-1">How do I cancel my subscription?</p>
              <p className="text-text-secondary">Go to Settings → Billing → Cancel subscription. Your plan remains active until the end of the billing period.</p>
            </div>
            <div>
              <p className="font-medium text-text mb-1">Can I change my plan later?</p>
              <p className="text-text-secondary">Yes, you can upgrade or downgrade at any time. Changes take effect immediately with prorated billing.</p>
            </div>
            <div>
              <p className="font-medium text-text mb-1">Is my data safe?</p>
              <p className="text-text-secondary">Yes. All data is encrypted, tenant-isolated with Row-Level Security, and never shared with third parties without consent. See our <a href="/privacy" className="text-accent hover:underline">Privacy Policy</a>.</p>
            </div>
            <div>
              <p className="font-medium text-text mb-1">What if I run out of AI tokens?</p>
              <p className="text-text-secondary">You'll be notified when you reach 80% of your plan's token limit. You can upgrade your plan or wait for the next billing cycle for a reset.</p>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-text-muted mt-8">
          By using PRACHAR, you agree to our <a href="/terms" className="text-accent hover:underline">Terms of Service</a> and <a href="/privacy" className="text-accent hover:underline">Privacy Policy</a>.
        </p>
      </div>
    </div>
  );
}
