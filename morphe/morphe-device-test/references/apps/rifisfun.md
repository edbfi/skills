# rif is fun: real-use checklist

How to check, on the test device and in the patched app, that each rif is fun patch does what it says. The patch
names are the ones in the patches repo's `docs/morphe/rifisfun.md` (its Patches table); that page wins on which
patches exist, what they do, their defaults and the tested version. Read it first, then run
[`scripts/checklist-gaps.sh`](../../scripts/checklist-gaps.sh) to see which entries below are missing or stale.

First full pass: 2026-11-17, **logged in**, a CLI build (`just morphe-patch`, Morphe CLI 2.2.0) of edbfi/apk-patches
at `fba9f12` plus a Morphe Manager 2.6.0 Save build of the same commit. Its per-patch table is in
edbfi/apk-patches#49. Checks that PR body doesn't show name the source "device run 2026-11-17": that run's notes,
logs and screenshots are with the owner (the patches repo's ignored `tmp/evidence/`). The checks were first written
for another patcher's build of the same patches, logged out, on 2026-11-16; the logged-out checks weren't repeated,
because nobody but the owner may log the app back in. A bare `#N` below is an edbfi/apk-patches PR.

## Contents

- App facts
- Set-up for every run
- Baseline after every install
- Patches (one entry per patch, in the docs' order)
- Checks that need two builds
- Known issues
- Unverified

## App facts

Facts a tester needs that the patches repo doesn't state. Re-check them against the docs and the file in hand; where
they disagree, the docs and the file win and this list needs a fix.

- **Package:** the docs' Tested version table names it; the commands below call it `$pkg`.
- **Original signer:** certificate SHA-256 `b8d15967759f795d29051f88ea0bcbf0bc5b6a7a587529c30856a73119c33cfd`,
  `CN=Andrew Shu`, one signer, v1 + v2 schemes, no source stamp. Seen with `apksigner verify --print-certs -v` on
  2026-11-16, matched by the owner against APKMirror's listing, and seen again on 2026-11-17.
- **A file seen before:** the APKMirror 5.6.22 file used on 2026-11-16 and 2026-11-17 had SHA-256
  `88d39f859c850f51542c6a12d8bd3c79706debe0f1dff061ed0fe32b3dc688e1` (versionCode 4622). It only tells you whether
  you hold that same file.
- **Packaging:** one universal plain APK (ABIs arm64-v8a, armeabi-v7a, x86, x86_64; nodpi; `classes.dex` to
  `classes3.dex`), no splits, 12795917 bytes. The CLI and Manager take it as it is (Manager's log: `split=false`).
- **Launch:** the launcher activity resolves to `<package>/.MainActivity`; `am start -W -n "$pkg/.MainActivity"`.
- **Link handling:** `am start -a android.intent.action.VIEW -d "'<url>'" -p "$pkg"` opens reddit.com, redd.it and
  v.redd.it URLs (`/r/`, `/comments/`, `/gallery/`, `/u/…/s/…`). rif has **no** intent filter for `imgur.com`,
  `redgifs.com` or `reddit.com/domain/…`: reach those through a Reddit post (its thumbnail or a link in its text).
  YouTube links open with an explicit component: `-n "$pkg/.MainActivity"`.
- **In-app link dialog:** tapping a link in a comment or self post opens a dialog with the label, `link N of M`,
  `◀ PREV`, `NEXT ▶`, the URL, `SHARE`, `COPY` and `GO` (uiautomator dump, 2026-11-16). Stepping with NEXT is the
  way to find a link whose URL a label hides.
- **Settings file:** `/data/data/$pkg/shared_prefs/settings.xml` holds `VIDEO_AUTOPLAY` (`NEVER` on the test
  device), `ADS_ENABLED`, `THREADS_CARDS`. Read it with `adb shell "su 0 cat …"`; never print `credentials.xml`
  values (it holds tokens). Login state: `adb shell dumpsys account` (`Accounts: 0` = logged out) plus
  `credentials.xml` key names only.
- **Resources:** the APK's resource file names are obfuscated (`res/EQ.xml`, not `res/layout/…`). Find a layout's
  file with `aapt2 dump resources <apk> | grep -A1 'layout/<name>$'`.
- **Extension:** package `app.edbfi.extension.rifisfun`, `extensions/edbfi/rifisfun.mpe` (35 classes in the `fba9f12`
  build), log tag `edbfi`: `adb logcat -d -s edbfi:*`. On every start it logs `I edbfi: Unpinned api.redgifs.com`
  (Fix Redgifs' pin hook). Its prefs, `app.edbfi.extension.rifisfun.xml`, hold `app_token_client` =
  `<client ID>:<sha256>` (Spoof client's token marker).
- **Video:** ExoPlayer logs `ExoPlayerImpl: Init` when a player starts. `adb logcat -d | grep -c 'ExoPlayerImpl:
  Init'` must stay 0 for a whole run. The Redgifs lookup runs only inside the video viewer (its callers in 5.6.22
  are the video browser fragment, the Redgifs viewer and the Gfycat lookup), so it can't be triggered without
  playback.
- **Cards:** rif turns Cards on by itself for image-heavy subreddits ("Activated Cards for images", with SETTINGS and
  Dismiss) and stores that per subreddit in `reddits.db`; `THREADS_CARDS` is the global switch. With autoplay Never,
  a video card shows a still.
- **Root:** the Redroid image is `userdebug`; the run read app files with `adb shell su 0 …` only.

## Set-up for every run

The run directory block in [evidence.md](../evidence.md) sets `ANDROID_SERIAL`, `TMP`, `RUN`, `UI_OUT` and `UI`; run
it once, then:

```bash
pkg=<package>                         # from the docs' Tested version table
```

A helper that opens a URL and keeps the dump, screenshot and logcat (the 2026-11-16 run kept it in `$RUN/bin/`,
outside any download directory, and so did the 2026-11-17 run):

```bash
open() {  # open <url> <name> [secs] [component]
  adb logcat -c
  if [[ -n ${4:-} ]]; then adb shell am start -a android.intent.action.VIEW -d "\"$1\"" -n "$4"
  else adb shell am start -a android.intent.action.VIEW -d "\"$1\"" -p "$pkg"; fi
  sleep "${3:-8}"; "$UI" shot "$2"; "$UI" dump > "$RUN/logs/$2-ui.txt"; adb logcat -d > "$RUN/logs/$2-logcat.txt"
}
```

## Baseline after every install

1. Record the install times, update the app in place, and compare (`firstInstallTime` unchanged, `lastUpdateTime`
   moved, `Success`). If `adb install -r` fails on the signature, stop: never uninstall.
2. Before launching, confirm autoplay is off from the settings file:
   `adb shell "su 0 cat /data/data/$pkg/shared_prefs/settings.xml" | grep -oE 'name="VIDEO_AUTOPLAY">[A-Z]+'` must
   print `NEVER`. If it doesn't, or the file is missing, don't launch: ask the owner to set it through scrcpy.
3. `adb logcat -c`, `adb shell am start -W -n "$pkg/.MainActivity"`, wait 12 s. Pass: a pid and focus on
   `<package>/…MainActivity`.
4. The front page loads: the dump shows `reddit: the front page of the internet` and post rows (titles start with
   `‎`, a left-to-right mark). Logged in, the overflow menu shows **Logout**; logged out it shows **Login** instead.
   Never log out to check the other form.
5. `adb logcat -d | grep -E 'FATAL EXCEPTION|NoClassDefFound|VerifyError|ClassNotFound|edbfi'`. Pass: none of the
   first four; `edbfi` lines are the extension's own (`Unpinned api.redgifs.com` is expected).

Status:

- Steps 1, 3–5: verified 2026-11-17, edbfi/apk-patches#49 (CLI and Manager builds, logged in: Logout item, Inbox
  loads; no FATAL, `VerifyError` or 401/403).
- Step 2: verified 2026-11-17, device run 2026-11-17 (`NEVER`).

## Patches

### Disable ads

- **Changes:** `AdViewHelper`/`ImageAlbumAdViewHelper` lifecycle methods return at once;
  `AdsGdprHelper.initAdsSdkWithListener` returns; the album adapter skips ad slots; the thread lists' native-ad check
  reads false; the dual-pane banner check returns false; `AppLovinInitProvider.onCreate` and
  `MobileAdsInitProvider.attachInfo` return before starting their SDKs. `ADS_ENABLED` is left alone.
- **Check:**
  1. Cold start (`am force-stop`, `logcat -c`, Baseline step 3), then scroll the front page about 12 screens, dumping
     each: `"$UI" dump | cut -f6 | grep -iE '^ad$|Loading ad|sponsored|promoted'`. Pass: nothing. Before the patch
     the 4th row was a native ad with an "ad" badge (#34).
  2. `adb logcat -d | grep -ciE 'applovin|googleads|doubleclick|googlesyndication|MobileAds|afma-sdk'`. Pass: 0.
  3. A Reddit gallery and an Imgur album open with no ad slot between images (Fix galleries, Fix Imgur).
  4. With **Ads** off as well (Enable golden platinum, step 3), the same three hold.
  5. The consent form and the dual-pane banner: not reachable on the test device (no GDPR region, phone layout).
- **Needs:** network.
- **Status:**
  - Steps 1–2: verified 2026-11-17, edbfi/apk-patches#49 (0 ad rows in 137 rows over 12 screens, 0 SDK lines).
  - Steps 3–4: verified 2026-11-17, device run 2026-11-17 (a gallery and Imgur posts with Ads off).
  - Step 5: unverified: confirm on the next run (needs a GDPR region or a tablet layout).

### Enable golden platinum

- **Changes:** the 24 pro checks (`"…redditdonation".equals(getPackageName()) || ADS_ENABLED`) read true; Synccit
  forced off and hidden; new post notifications' push-backend check false and its category hidden; the downloadable
  theme list and its Refresh hidden; "Upgrade to Pro" hidden; settings take the paid build's path; "Ads & pro
  features" becomes **Ads**, summary "Pro features stay on either way".
- **Check:**
  1. More options → **Settings** → **General settings**: a row **Ads** with summary **Pro features stay on either
     way**; **Moderator features** is enabled.
  2. **About** has no "Upgrade to Pro"; **Notifications** has no new post notifications category; **History** has no
     Synccit (only "Sync history via reddit", which needs Premium).
  3. Tap **Ads** to turn it off (check `ADS_ENABLED` false in the settings file). Then Appearance → **Theme**: the
     screen shows **Main themes**, **Cards**, **Black BG for dark themes** and **Theme developer options**, no
     downloadable theme list. Tap **Cards**: no "Cards are pro" dialog, `THREADS_CARDS` true. Cold start: the front
     page renders as cards. Open a Reddit gallery and an Imgur album (Fix galleries, Fix Imgur): both native.
  4. **Appearance**: **Dual pane** enabled, with no "Requires ads enabled" in its summary.
  5. Set back what you changed: **Ads** on, **Cards** off; diff the settings file against the one saved at the start
     (no difference).
  6. Moderator tools (mod account), visited-links sync (Premium), dual pane in landscape, theme folder
     (#38's `manifest.json` steps).
- **Needs:** network; for step 6 a moderator account or Reddit Premium (the owner's login).
- **Status:**
  - Steps 1–3: verified 2026-11-17, device run 2026-11-17 (edbfi/apk-patches#49 shows only the summary: Ads/Pro
    features stay on, no Upgrade or Synccit, cards without a "pro" dialog).
  - Steps 4–5: verified 2026-11-17, device run 2026-11-17 (Dual pane's summary "Tablet recommended."; the settings
    file's keys equal the start's).
  - Step 6: unverified: confirm on the next run.

### Fix /s/ links

- **Changes:** the in-app link opener, `MainActivity`'s intent link handler and `UserPathDummyActivity.onCreate` hand
  share links to `ShareLinks`, which forwards them to `RedditMailClickDummyActivity`; that activity stays open while
  one GET (Reddit UA, no token, no redirects) reads `Location`, then routes the target minus `share_id` and `utm_*`.
  On failure: toast "Could not open the share link" and the app's browser.
- **Check:**
  1. From outside: `open 'https://www.reddit.com/r/chicago/s/UBknncuPg6' slink 12`. Pass: logcat `START` lines go
     `MainActivity` → `.intentfilter.RedditMailClickDummyActivity` ×2 → `MainActivity`, and the dump shows the post
     "The bean- 1, Chicagoans 0" with its comments.
  2. `/u/` form: `open 'https://www.reddit.com/u/spez/s/AbCdEf1234' slink-user` (a made-up code Reddit redirects to
     the profile). Pass: `UserPathDummyActivity` → router ×2 → `.user.ProfileActivity`, dump shows `overview for
     spez`.
  3. In app: `open 'https://www.reddit.com/r/comics/comments/1wuwu8p/' slink-inapp` (a self post listing other
     posts), tap any link in its text, step with `NEXT ▶` until the URL is
     `https://www.reddit.com/r/comics/s/eITN24Wlls` (link 64 of 110 on 2026-11-16), tap **GO**. Pass: router ×2 →
     `MainActivity` on the post it points to.
  4. No `edbfi` "Could not resolve" or "No post for" warning, no crash.
  5. The failure fallback (toast, then the app's browser).
- **Needs:** network; public share links (those above are from #31 and a saved r/comics listing).
- **Status:**
  - Steps 1–4: verified 2026-11-17, edbfi/apk-patches#49 (CLI; step 1 also on the Manager build).
  - Step 5: unverified: confirm on the next run.

### Fix galleries

- **Changes:** a `RequestHook` handler answers `/api/info.json?id=t3_<one post>` (403) from
  `/comments/<id>.json?limit=1`, after checking the page holds that post; gallery entries Reddit marks `failed` get
  their extension from `m`, the thumbnail, or bounded HEAD lookups on i.redd.it, and images not found are dropped.
- **Check:**
  1. `open 'https://www.reddit.com/gallery/1xnx8tw' gallery-failed 10`. Pass: the dump shows the title, `2 images`
     and two `Image` nodes, and both images render (screenshot). Both of its images are `failed` on Reddit.
  2. `open 'https://www.reddit.com/gallery/1xwowwb' gallery 10`. Pass: `14 images`.
  3. No `Error loading`, no `edbfi` warning.
  4. Inline v.redd.it player: never open it (playback).
- **Needs:** network.
- **Status:**
  - Steps 1–3: verified 2026-11-17, edbfi/apk-patches#49 (CLI and Manager builds).
  - Step 4: unverified: confirm on the next run (not checkable without playback; #32 replayed the request on the
    host instead).

### Fix Imgur

- **Changes:** the album request task parses `Imgur.album(url)` (api.imgur.com `album/<id>`, falling back to
  `image/<id>` as an album of one) instead of the dead `api.redditisfun.com` proxy; the thumbnail loader's two cover
  lookups return `Imgur.cover(link)` (cover, else first image); titles are cut from `/a/<title>-<id>` and
  `/gallery/<title>-<id>`.
- **Check:**
  1. Album and thumbnail: open a subreddit whose posts link Imgur albums and scroll until a row reads `imgur album`
     (on 2026-11-16 `open 'https://www.reddit.com/r/MarvelCards/new/' marvel 10` found "Sketch cards for sale",
     `imgur.com/a/uMFYcoe`, an album with an empty cover; on 2026-11-17 r/MarvelCards had none, and r/Watchexchange
     did).
     Pass: the card shows the album's image. Tap the image: the dump shows `N images`, `Image` nodes and
     `imgur.com/a/<id>` in the toolbar; no `WebView`, no `edbfi` "Imgur album failed".
  2. Titled link: `open 'https://www.reddit.com/r/MadeMeSmile/comments/1xma7qh/' imgur-titled`, tap **Thumbnail**.
     Pass: the native viewer with the post's title, `1 image`, toolbar `imgur.com/gallery/90-years-old-…-CroPyfF`.
     It is an animation: don't tap **Play animation**.
  3. A `/gallery/` single image (#35 used `imgur.com/gallery/p1pokdr` in r/OldSchoolCool) opens as
     `1 image`.
  4. Uploads fail (Known issue).
- **Needs:** network; Reddit posts linking Imgur (rif can't open imgur.com URLs from `am start`).
- **Status:**
  - Step 1: verified 2026-11-17, edbfi/apk-patches#49 (through r/Watchexchange: `imgur.com/a/2wXKcxF`, 14 images).
  - Step 2: verified 2026-11-17, device run 2026-11-17 (with Ads off).
  - Step 3: unverified: confirm on the next run (step 2 covers the `/gallery/` path with a title).

### Fix load more comments

- **Changes:** a `RequestHook` handler turns the app's `POST api/morechildren.json` (403) into a GET of the first
  wanted comment's page, then builds the `{"json":{"data":{"things":[…]}}}` reply from the parent's page or one page
  per comment (4 at a time, at most 20 per tap; leftovers come back as a new row).
- **Check:**
  1. `open 'https://www.reddit.com/r/AskReddit/comments/1xsg0uh/' more 10`, then scroll until
     `"$UI" dump 'load [0-9]+ more comment'` matches (first screen down on 2026-11-16: `load 4 more comments`).
     `adb logcat -c`, tap it, wait 6 s, dump. Pass: the row is gone and replies appear at increasing indent (x 170 →
     196 → 223 on 2026-11-16); no `edbfi` "Parent comment failed" or "Comment … failed", no 403.
  2. A top-level row past 20 comments, and the same logged in.
- **Needs:** network; a large thread.
- **Status:**
  - Step 1, and step 2 logged in: verified 2026-11-17, edbfi/apk-patches#49 (CLI and Manager builds).
  - Step 2's top-level row past 20 comments: unverified: confirm on the next run.

### Fix markdown links

- **Changes:** the TagSoup body-to-text method (anchored on `"Error parsing HTML"`) first calls `MarkdownLinks.fix`,
  which turns Reddit's leftover `[label](<a href="H">target</a>)` into `<a href="H">label</a>`.
- **Check:**
  1. `open 'https://www.reddit.com/r/pics/comments/1xs3nmh/_/19seuus4d5rfl/' markdown 10`. Pass: a clickable node
     reads `r/scams` and `grep -c '](' "$RUN/logs/markdown-ui.txt"` is 0 (before: `[r/scam](r/scam)[s](r/scam)`).
  2. Tap it: the link dialog shows `link 1 of 2` and `https://www.reddit.com/r/scam`. Press BACK.
  3. No `edbfi` "Fix markdown links failed".
- **Needs:** network.
- **Status:** verified 2026-11-17, edbfi/apk-patches#49 (CLI and Manager builds).

### Fix media links

- **Changes:** at the start of the in-app link opener, `reddit.com/media?url=<https i.redd.it | preview.redd.it |
  external-preview.redd.it URL>` is replaced by the wrapped URL.
- **Check:**
  1. `open 'https://www.reddit.com/r/sanantoniospurs/comments/1xsurb3/' medialink` ("Wemby The Dunker", a
     `reddit.com/media` link), `adb logcat -c`, `"$UI" tap '^Thumbnail'`, wait 7 s. Pass: rif's image viewer with
     `preview.redd.it/9lnkivsjus0i1.jpeg…` in its toolbar and the image shown.
- **Needs:** network.
- **Status:** verified 2026-11-17, edbfi/apk-patches#49.

### Fix Redgifs

- **Changes:** the Redgifs lookup's token getter returns `Redgifs.token(status)` (Redgifs' temporary token, system
  User-Agent, cached to the JWT's `exp`); the lookup sends the system User-Agent; the gif ID is lowercased; the
  client factory's pins for `api.redgifs.com` are dropped (`I edbfi: Unpinned api.redgifs.com`).
- **Check:**
  1. Baseline: every start logs `I edbfi: Unpinned api.redgifs.com` once.
  2. Host probe (no device; only shows Redgifs still behaves as the fix expects):
     `curl -A '<a browser UA>' https://api.redgifs.com/v2/auth/temporary` → 200 with a token; with that token and UA,
     `/v2/gifs/<lowercase id>` → 200 and `/v2/gifs/<MixedCase id>` → 404; another UA → 401.
  3. The lookup in the app: it runs only when rif's video viewer opens, which plays the video, and video crashes
     Redroid's SurfaceFlinger. #33 opened `redgifs.com/watch/PeskyShinyHarvestmouse` and saw
     ExoPlayer start: that is playback, so not a check for this skill. A no-playback check needs a hook in the
     running app (Frida, `adb root`), only with the owner's agreement.
- **Needs:** network; for step 3 the owner's agreement to root and a hook, or a device that can play video.
- **Status:**
  - Steps 1–2: verified 2026-11-17, edbfi/apk-patches#49.
  - Step 3: unverified: confirm on the next run (see Needs).

### Fix YouTube player

- **Changes:** the IFrame player options builder's `https://www.youtube.com` literal becomes
  `https://com.andrewshu.android.reddit`: the `origin` player var, the page's base URL and so the Referer.
- **Check:**
  1. `open 'https://www.youtube.com/watch?v=jNQXAC9IVRw' youtube 14 "$pkg/.MainActivity"` (YouTube's first public
     video). Pass: `grep -aoE 'youtube\.com/embed/\?[^ ,"]*' "$RUN/logs/youtube-logcat.txt"` shows `autoplay=0` and
     `origin=https%3A%2F%2Fcom.andrewshu.android.reddit`; the screen shows the video's title and channel with a play
     button (cued); no "There was an error initializing the YouTubePlayer (Error code: 0)" toast. **Never tap play**;
     `ExoPlayerImpl: Init` stays 0.
  2. Playback and the `t=` offset; the native player with the YouTube app installed.
- **Needs:** network.
- **Status:**
  - Step 1: verified 2026-11-17, edbfi/apk-patches#49 (cued, not played).
  - Step 2: unverified: confirm on the next run (playback, and no YouTube app, on Redroid).

### Keep typed text in view

- **Changes:** resource-only: in `comment_reply_dialog`, `compose_message_dialog`, `compose_modmail_dialog` and
  `modmail_reply_dialog`, the ScrollView's `padding` becomes a `layout_margin` of the same value.
- **Check:**
  1. Build check (no device). For each of the four layouts, find its file (App facts, Resources), then
     `aapt2 dump xmltree --file <res/….xml> <patched.apk>`. Pass: the ScrollView has `android:layout_margin`
     (`@dimen` 16dp, or `5.000000dp` in `compose_message_dialog`) and no `android:padding`; a `padding` further down
     belongs to another view. The original APK has `android:padding` there.
  2. On the device, logged in: open a reply box on any post (never send), type 25 lines of throwaway text with
     `"$UI" type` and `adb shell input keyevent ENTER`, then screenshot. Pass: the line being typed and its underline
     are whole above the keyboard. Before: it was cut in half at the box's bottom edge. Cancel and discard. Logged
     out, rif answers "Please login to reply." and the box can't be opened.
- **Needs:** for step 2 the owner's login.
- **Status:** verified 2026-11-17, edbfi/apk-patches#49 (step 1 on the patched and the original APK; step 2 with
  26 lines).

### Spoof client

- **Changes:** the authorize URL (`www.reddit.com/api/v1/authorize`), the Basic auth of every token request, the
  redirect URI and the User-Agent take the options (RedReader's installed-app client by default); every Reddit API
  URL except the token endpoint uses the app-only token when logged out; the cached app-only token is tied to its
  client ID (`app_token_client`).
- **Check:**
  1. Logged out: the Baseline's front page, a subreddit and a thread with comments load. Only when the device has no
     account already; never log out to check it.
  2. `adb shell "su 0 cat /data/data/$pkg/shared_prefs/app.edbfi.extension.rifisfun.xml"`: `app_token_client` is
     `yH0aTnJEt6qUgGn835B4vg:<sha256>` (RedReader's client ID).
  3. Across the run's logs, `grep -aE '(oauth|www)\.reddit\.com' | grep -aE ' 40[13]|Unexpected response code'` is
     empty.
  4. Logged in (the owner logs in through scrcpy, Reddit's Log In page in rif's WebView): the front page and inbox
     load logged in, and stay so after `adb install -r` and after the token's hourly refresh. Don't record the
     inbox's title: it holds the account name.
  5. Options in Manager: the patch's options are `OAuth client ID`, `Redirect URI` and `User-Agent`, with the
     defaults the docs' Options section describes. The CLI takes them after the patch's `-e`
     (`-e "Spoof client" -O "<key>=<value>"`).
- **Needs:** network; step 1 a device with no account; step 4 the owner's login.
- **Status:**
  - Steps 2–3, and step 4 after `adb install -r`: verified 2026-11-17, edbfi/apk-patches#49 (CLI and Manager
    builds).
  - Step 1: unverified: confirm on the next run (the app was logged in, and only the owner may log it back in).
  - Step 4 across the token's hourly refresh: unverified: confirm on the next run.
  - Step 5: unverified: confirm on the next run (Manager's options screen wasn't recorded).

## Checks that need two builds

- **CLI build against Manager's Save build.** Run the full list on the CLI build; on the Manager build the Baseline
  plus Fix /s/ links, Fix galleries (`1xnx8tw`), Fix markdown links, Fix load more comments and Spoof client, all of
  which go through the extension (the 2026-11-17 set), after the CRC check in
  [apk-provenance.md](../apk-provenance.md) section 5.
- **Manager's own source** had no patches for rif is fun on 2026-11-17, so Manager's default selection was the repo's
  patches only ([manager.md](../manager.md) section 9).
- **Ads off.** Enable golden platinum and Disable ads interact through the **Ads** setting: check both with it on and
  off (Disable ads step 4, Enable golden platinum step 3), then set it back.

## Known issues

Read the Known issues section of the patches repo's `docs/morphe/rifisfun.md` before reporting a failure. A symptom
it lists (Imgur uploads failing; Synccit, new post notifications and downloadable themes gone) is expected; report it
as a known issue, not as a failure. A symptom it doesn't list is a finding.

## Unverified

Checks marked `unverified: confirm on the next run`:

- Disable ads (step 5)
- Enable golden platinum (step 6)
- Fix /s/ links (step 5)
- Fix galleries (step 4)
- Fix Imgur (step 3)
- Fix load more comments (step 2, top-level row)
- Fix Redgifs (step 3)
- Fix YouTube player (step 2)
- Spoof client (step 1, step 4 across a token refresh, step 5)
