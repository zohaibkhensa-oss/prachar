export const dynamicParams = false;

export function generateStaticParams() {
  return [{ channel: "placeholder" }];
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
