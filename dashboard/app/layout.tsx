import "./globals.css";

export const metadata = {
  title: "Agentic Go Contributor",
  description: "Dashboard for reviewing AI-generated patches",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
