import { getPageImage, getPageMarkdownUrl, source } from '@/lib/source';
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
  MarkdownCopyButton,
  ViewOptionsPopover,
} from 'fumadocs-ui/layouts/docs/page';
import { notFound } from 'next/navigation';
import { getMDXComponents } from '@/components/mdx';
import type { Metadata } from 'next';
import { createRelativeLink } from 'fumadocs-ui/mdx';
import { gitConfig } from '@/lib/shared';

export default async function Page(props: PageProps<'/docs/[[...slug]]'>) {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  const MDX = page.data.body;
  const markdownUrl = getPageMarkdownUrl(page).url;

  /* Section pip above the title (e.g. "Internals"). Skips the docs index and
     top-level pages, where the slug carries no parent section. */
  const sectionLabel = formatSectionLabel(page.slugs);

  return (
    <DocsPage toc={page.data.toc} full={page.data.full}>
      {sectionLabel && (
        <div className="mb-3 flex items-center gap-2">
          <span className="font-mono text-[10.5px] tracking-[0.18em] uppercase text-fd-primary">
            §
          </span>
          <span className="font-mono text-[11px] tracking-[0.16em] uppercase text-fd-muted-foreground">
            {sectionLabel}
          </span>
        </div>
      )}
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription className="mb-0">{page.data.description}</DocsDescription>
      <div className="flex flex-row gap-2 items-center border-b pb-6">
        <MarkdownCopyButton markdownUrl={markdownUrl} />
        <ViewOptionsPopover
          markdownUrl={markdownUrl}
          githubUrl={`https://github.com/${gitConfig.user}/${gitConfig.repo}/blob/${gitConfig.branch}/content/docs/${page.path}`}
        />
      </div>
      <DocsBody>
        <MDX
          components={getMDXComponents({
            a: createRelativeLink(source, page),
          })}
        />
      </DocsBody>
    </DocsPage>
  );
}

function formatSectionLabel(slugs: string[]): string | null {
  /* Only render the label for nested pages. For top-level entries the H1
     already shows the same word, so the pip would just be noise. */
  if (slugs.length < 2) return null;
  return slugs[0].replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export async function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata(props: PageProps<'/docs/[[...slug]]'>): Promise<Metadata> {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  return {
    title: page.data.title,
    description: page.data.description,
    openGraph: {
      images: getPageImage(page).url,
    },
  };
}
