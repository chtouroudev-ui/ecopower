import { Helmet } from 'react-helmet-async';

const SITE = 'https://eco-power.tn';

export const SEO = ({ title, description, path = '/', noindex = false }) => {
  const url = SITE + path;
  return (
    <Helmet>
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={url} />
      <meta property="og:url" content={url} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      {noindex && <meta name="robots" content="noindex, nofollow" />}
    </Helmet>
  );
};