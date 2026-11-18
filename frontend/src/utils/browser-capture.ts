export type BrowserCapturePayload = {
  version: 1;
  url: string;
  title: string;
  text: string;
  page_type: "article" | "image" | "video";
  image_urls: string[];
  has_video: boolean;
  subtitle_text: string;
  video_duration?: number;
  captured_at: string;
};

function collectPageForKnowFlow(captureUrl: string) {
  const run = () => {
    const clean = (value: unknown) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/[ \t]+/g, " ")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
    const addUnique = (items: string[], value: unknown) => {
      const text = clean(value);
      if (text && !items.includes(text)) items.push(text);
    };
    const absoluteUrl = (value: unknown) => {
      try {
        const url = new URL(String(value || ""), location.href);
        return /^https?:$/.test(url.protocol) ? url.href : "";
      } catch {
        return "";
      }
    };

    const textParts: string[] = [];
    const imageUrls: string[] = [];
    const selectedText = clean(window.getSelection()?.toString());
    if (selectedText) addUnique(textParts, selectedText);

    const metadata = (selector: string) =>
      document.querySelector<HTMLMetaElement>(selector)?.content || "";
    let title = clean(
      metadata('meta[property="og:title"]') ||
        metadata('meta[name="twitter:title"]') ||
        document.querySelector<HTMLElement>("#detail-title")?.innerText ||
        document.querySelector<HTMLElement>("article h1")?.innerText ||
        document.title,
    );
    const subtitleParts: string[] = [];
    let stateHasVideo = false;
    addUnique(textParts, metadata('meta[property="og:description"]'));
    addUnique(textParts, metadata('meta[name="description"]'));

    const platformSelectors = [
      "#detail-desc",
      "#detail-title",
      ".note-content .title",
      ".note-content .desc",
      '[class*="note-content"]',
      '[class*="noteContent"]',
      "article",
      "main",
    ];
    for (const selector of platformSelectors) {
      document.querySelectorAll<HTMLElement>(selector).forEach((element) => {
        if (element.offsetParent !== null || element.tagName === "ARTICLE") {
          addUnique(textParts, element.innerText);
        }
      });
    }

    const jsonImages: unknown[] = [];
    const visitStructuredData = (value: unknown) => {
      if (Array.isArray(value)) {
        value.forEach(visitStructuredData);
        return;
      }
      if (!value || typeof value !== "object") return;
      const item = value as Record<string, unknown>;
      const type = String(item["@type"] || "").toLowerCase();
      if (
        ["article", "newsarticle", "socialmediaposting", "videoobject"].some(
          (candidate) => type.includes(candidate),
        )
      ) {
        addUnique(textParts, item.headline);
        addUnique(textParts, item.description);
        addUnique(textParts, item.articleBody);
        addUnique(textParts, item.caption);
      }
      for (const key of ["image", "thumbnailUrl", "contentUrl"]) {
        const media = item[key];
        if (Array.isArray(media)) jsonImages.push(...media);
        else if (media) jsonImages.push(media);
      }
      Object.values(item).forEach(visitStructuredData);
    };
    document
      .querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]')
      .forEach((script) => {
        try {
          visitStructuredData(JSON.parse(script.textContent || "null"));
        } catch {
          // Invalid third-party structured data must not stop the capture.
        }
      });

    // Xiaohongshu and similar SPA pages keep the complete carousel in an
    // in-page note object even when only one or two slides are mounted in the
    // DOM. Bookmarklets execute in the page world, so this can read that data
    // without exporting login cookies or reverse-engineering request signing.
    const pageWindow = window as Window & {
      __INITIAL_STATE__?: unknown;
      __NUXT__?: unknown;
    };
    const stateRoot = pageWindow.__INITIAL_STATE__ || pageWindow.__NUXT__;
    if (stateRoot && typeof stateRoot === "object") {
      const candidates: Array<{ score: number; value: Record<string, unknown> }> = [];
      const visited = new WeakSet<object>();
      let inspected = 0;
      const inspect = (value: unknown, depth = 0) => {
        if (
          !value ||
          typeof value !== "object" ||
          visited.has(value) ||
          depth > 9 ||
          inspected > 12_000
        ) {
          return;
        }
        visited.add(value);
        inspected += 1;
        if (Array.isArray(value)) {
          value.forEach((item) => inspect(item, depth + 1));
          return;
        }
        const item = value as Record<string, unknown>;
        let score = 0;
        if (typeof item.title === "string") score += 2;
        if (typeof item.desc === "string" || typeof item.description === "string") {
          score += 3;
        }
        if (Array.isArray(item.imageList) || Array.isArray(item.images)) score += 5;
        if (item.video || item.videoInfo) score += 5;
        if (item.noteId || item.note_id || item.noteType || item.type) score += 2;
        if (score >= 5) candidates.push({ score, value: item });
        try {
          Object.values(item).forEach((child) => inspect(child, depth + 1));
        } catch {
          // Ignore reactive proxies with throwing getters.
        }
      };
      inspect(stateRoot);
      candidates.sort((a, b) => b.score - a.score);
      const note = candidates[0]?.value;
      if (note) {
        title = clean(note.title) || title;
        addUnique(textParts, note.desc || note.description);
        const stateImages = Array.isArray(note.imageList)
          ? note.imageList
          : Array.isArray(note.images)
            ? note.images
            : [];
        stateImages.forEach((image) => {
          jsonImages.push(image);
          if (image && typeof image === "object") {
            const data = image as Record<string, unknown>;
            jsonImages.push(
              data.urlDefault,
              data.urlPre,
              data.url,
              data.src,
              ...(Array.isArray(data.urlList) ? data.urlList : []),
            );
            if (Array.isArray(data.infoList)) {
              data.infoList.forEach((info) => {
                if (info && typeof info === "object") {
                  jsonImages.push((info as Record<string, unknown>).url);
                }
              });
            }
          }
        });
        stateHasVideo = Boolean(note.video || note.videoInfo);
        const videoData = (note.video || note.videoInfo) as
          | Record<string, unknown>
          | undefined;
        if (videoData) {
          addUnique(subtitleParts, videoData.subtitle || videoData.caption);
        }
      }
    }

    const addImage = (value: unknown) => {
      const url = absoluteUrl(
        typeof value === "object" && value
          ? (value as Record<string, unknown>).url ||
              (value as Record<string, unknown>).contentUrl
          : value,
      );
      if (
        url &&
        !/\.(svg|ico)(?:[?#]|$)/i.test(url) &&
        !imageUrls.includes(url)
      ) {
        imageUrls.push(url);
      }
    };
    addImage(metadata('meta[property="og:image"]'));
    jsonImages.forEach(addImage);

    const preferredImages = document.querySelectorAll<HTMLImageElement>(
      'article img, main img, [class*="swiper"] img, [class*="carousel"] img, [class*="note"] img',
    );
    const imageElements = preferredImages.length
      ? preferredImages
      : document.querySelectorAll<HTMLImageElement>("img");
    imageElements.forEach((image) => {
      const width = image.naturalWidth || image.width;
      const height = image.naturalHeight || image.height;
      const label = `${image.className} ${image.alt}`.toLowerCase();
      if (
        (width >= 300 || height >= 300 || /xhscdn|sns-img/.test(image.currentSrc)) &&
        !/avatar|icon|logo|emoji/.test(label)
      ) {
        addImage(image.currentSrc || image.src);
      }
    });

    const videos = Array.from(document.querySelectorAll<HTMLVideoElement>("video"));
    const hasVideo =
      stateHasVideo ||
      videos.length > 0 ||
      Boolean(metadata('meta[property="og:video"]')) ||
      Boolean(metadata('meta[property="og:video:url"]'));
    videos.forEach((video) => addImage(video.poster));

    videos.forEach((video) => {
      Array.from(video.textTracks || []).forEach((track) => {
        Array.from(track.cues || []).forEach((cue) => {
          const cueText = "text" in cue ? String(cue.text) : "";
          addUnique(subtitleParts, cueText);
        });
      });
    });
    document
      .querySelectorAll<HTMLElement>(
        '.subtitle, .captions, [class*="subtitle"], [class*="caption-text"]',
      )
      .forEach((element) => addUnique(subtitleParts, element.innerText));

    if (!textParts.some((part) => part.length >= 20)) {
      addUnique(textParts, document.body?.innerText?.slice(0, 80_000));
    }

    const duration = videos.find(
      (video) => Number.isFinite(video.duration) && video.duration > 0,
    )?.duration;
    const payload: BrowserCapturePayload = {
      version: 1,
      url: location.href,
      title,
      text: clean(textParts.join("\n\n")).slice(0, 120_000),
      page_type: hasVideo ? "video" : imageUrls.length > 1 ? "image" : "article",
      image_urls: imageUrls.slice(0, 10),
      has_video: hasVideo,
      subtitle_text: clean(subtitleParts.join("\n")).slice(0, 120_000),
      ...(duration ? { video_duration: Math.round(duration * 10) / 10 } : {}),
      captured_at: new Date().toISOString(),
    };

    const json = JSON.stringify(payload);
    const bytes = new TextEncoder().encode(json);
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    const encoded = btoa(binary);
    const target = `${captureUrl}#capture=${encodeURIComponent(encoded)}`;
    const opened = window.open(target, "_blank");
    if (!opened) {
      window.open(target, "_self");
      return;
    }
    void navigator.clipboard.writeText(json).catch(() => {
      // The URL fragment remains the primary transport and never reaches the server.
    });
  };
  run();
}

export function createBrowserCollectorBookmarklet(captureUrl: string) {
  return `javascript:(${collectPageForKnowFlow.toString()})(${JSON.stringify(
    captureUrl,
  )})`;
}

export function decodeCaptureFragment(value: string): BrowserCapturePayload {
  const binary = atob(decodeURIComponent(value));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes)) as BrowserCapturePayload;
}

export function parseCaptureText(value: string): BrowserCapturePayload {
  const parsed = JSON.parse(value) as BrowserCapturePayload;
  if (
    parsed?.version !== 1 ||
    typeof parsed.url !== "string" ||
    typeof parsed.text !== "string" ||
    !Array.isArray(parsed.image_urls)
  ) {
    throw new Error("采集数据格式无效");
  }
  return parsed;
}
