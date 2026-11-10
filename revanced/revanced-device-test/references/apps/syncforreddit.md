# Sync for Reddit: real-use checklist

How to check, on the test device and in the patched app, that each Sync for Reddit patch does what it says. The
patch names are the ones in the patches repo's `docs/syncforreddit.md` (its Patches table); that page wins on which
patches exist, what they do, their defaults and the tested version. Read it first, then run
[`scripts/checklist-gaps.sh`](../../scripts/checklist-gaps.sh) to see which entries below are missing or stale.

No single full pass has been run yet. Each check was last confirmed on the device in the PR named in its Status,
between 2026-11-08 and 2026-11-09, on CLI builds (the patches repo's patch recipe) of the code at that PR.

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

- **Package:** the docs' Tested version table names it; the commands below call it `<package>` or `$pkg`. It is
  also what `aapt2 dump badging` prints for the original APK and what `dumpsys package` lists on the device.
- **Original signer:** certificate SHA-256 `0220976139f8d08d048ebd5bbf2f818c017e03aaab162403b92b6e9ade4d20eb`,
  `CN=Laurence Dawson`, plus a Google Play source stamp (stamp certificate SHA-256
  `3257d599a49d2c961a471ca9843f59d341a405884583fc087df4237b733bbd6d`, `CN=Android, OU=Android, O=Google Inc.`).
  This is the known value [apk-provenance.md](../apk-provenance.md) compares the original APK against. Seen with
  `apksigner verify --print-certs` on 2026-11-09 (same run).
- **A file seen before:** the v23.06.30-13:39 file used on 2026-11-09 had SHA-256
  `6469a8dcc8e2a097892f84e8962e94965713be327b18db6a3110ed96f7fa4190` (versionCode 23033). It only tells you whether
  you hold that same file; it says nothing about which version the patches are tested on (see the docs).
- **Packaging:** one universal plain APK (ABIs arm64-v8a, armeabi-v7a, x86, x86_64; nodpi), no splits. Both the CLI
  and Manager take it as it is.
- **Launch:** the launcher activity resolves to `<package>/.ui.activities.HomeActivity.Default`;
  the window that opens is `.ui.activities.MainActivity`. Starting `MAIN`/`LAUNCHER` by package alone
  (`am start -a … -c … -p <package>`) does not resolve; resolve the activity instead (Baseline step 3).
- **Link handler:** `am start -a android.intent.action.VIEW -d <url> -n <package>/.ui.activities.IntentActivity`
  opens a reddit.com or imgur.com URL as the app would (#12; Fix /s/ links reopens its targets through the same
  activity). Galleries and Imgur albums open in `.ui.activities.media.MultiImageActivity`; a failed album falls back
  to `.ui.activities.WebViewActivity`. For other Reddit URLs the sources used
  `am start -a android.intent.action.VIEW -d <url> -p <package>`, or the package as the last argument.
- **Media download job:** `.receiver.download.RetryReceiver` (not exported, so broadcast it as root) starts the
  app's download jobs (`DownloadRedditVideoJob`, `DownloadMediaJob`). On the test device the final copy to shared
  storage fails because no download folder has been picked, so the result stays in the app's cache,
  `/sdcard/Android/data/<package>/cache/images/<n>.mp4`, readable only as root (edbfi/revanced-patches#10).
- **Extension log tag:** the bundle's extension (`app.edbfi.extension.syncforreddit`) logs its warnings under the tag
  `edbfi`: `adb logcat -d -s edbfi:W`.
- **Root:** the Redroid image is `userdebug`. The #10 and #11 sessions read the app's private files with
  `adb shell su 0 …`; the #19 and #20 sessions used `adb root` and ended with `adb unroot`. Use root only for the
  reads and cache removals below.

## Set-up for every run

The run directory block in [evidence.md](../evidence.md) sets `ANDROID_SERIAL`, `TMP`, `RUN`, `UI_OUT` and `UI`; run
it once, then:

```bash
pkg=<package>                         # from the docs' Tested version table
```

Every file a check pulls from the device goes in a new directory under `$RUN/downloads/`; it is untrusted data.

## Baseline after every install

Applies to every build, CLI or Manager, before any patch check.

1. Record the install times, update the app in place, and compare:

   ```bash
   adb shell dumpsys package "$pkg" | grep -E 'firstInstallTime|lastUpdateTime'
   adb install -r <patched.apk>
   adb shell dumpsys package "$pkg" | grep -E 'firstInstallTime|lastUpdateTime'
   ```

   Pass: `Success`, `lastUpdateTime` moved, `firstInstallTime` unchanged. If `adb install -r` fails on the
   signature, stop: never uninstall (see [manager.md](../manager.md) on the keystore).
2. Clear the log: `adb logcat -c`.
3. Launch through the resolved activity:

   ```bash
   act=$(adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN \
     -c android.intent.category.LAUNCHER "$pkg" | tail -1 | tr -d '\r')
   adb shell am start -W -n "$act"
   sleep 12
   adb shell pidof "$pkg"
   adb shell dumpsys window | grep mCurrentFocus
   ```

   Pass: a pid, and focus on `<package>/…MainActivity`.
4. Confirm autoplay is off before anything else in the app: don't scroll the feed and don't open a post first. More
   actions → Settings → Search settings, type `autoplay`, open **Autoplay** (under Data options). Its summary must
   read **Never**; set it if not (the app's default is **WiFi only**). **Enhanced autoplay** (Experimental) must stay
   off. The setting is app data, so `adb install -r` keeps it and this is normally a confirmation; after a new login
   or on a device you know nothing about, it is the first thing to do. Never open a video in the app's viewer.
5. The app opens logged in to its feed: `"$UI" dump | grep -E 'Frontpage|Inbox'`, plus `"$UI" shot baseline`. A
   login page instead means the login is gone: stop and ask the owner to log in through scrcpy. Never record the
   account name.
6. Check the log:

   ```bash
   adb logcat -d | grep -E 'FATAL EXCEPTION|NoClassDefFound|VerifyError|ClassNotFound|edbfi'
   ```

   Pass: no `FATAL EXCEPTION`, `NoClassDefFoundError`, `VerifyError` or `ClassNotFoundException`. Lines tagged
   `edbfi` are the extension's own warnings: read them. A failed request it reports (for example a Reddit 504 on one
   comment page) is not a crash, but note it.

Status:

- Steps 1–3, 5 and 6: verified 2026-11-09, edbfi/revanced-patches#21 (Manager's Save APK build installed with
  `adb install -r`, `firstInstallTime` unchanged, feed loaded, no `FATAL` or `NoClassDefFoundError`).
- Step 4: verified 2026-11-08, device set-up before edbfi/revanced-patches#7 (Autoplay set from WiFi only to Never
  through the settings search).

## Patches

### Spoof client

- **Changes:** returns the option values from the app's redirect-URI, `Basic` auth-header and Reddit User-Agent
  methods, puts the client ID in the authorize URL, and rewrites every `https://ssl.reddit.com/` literal to
  `https://www.reddit.com/` (the token endpoint).
- **Check:**
  1. The Baseline's logged-in feed is this patch's main check: the feed loads logged in after `adb install -r`.
  2. Open the Inbox from the app: it loads.
  3. Look for refused API calls:

     ```bash
     adb logcat -d | grep -E 'Unexpected response code (401|403) for https://(oauth|www)\.reddit\.com'
     ```

     Pass: none for the feed or the token endpoint.
- **Needs:** the owner's login, network. Testing a non-default `OAuth client ID`, `Redirect URI` or `User-Agent`
  needs the accounts removed and added again (docs, Options): that is a new login, so leave it to the owner.
- **Status:**
  - Steps 1–2: verified 2026-11-08, edbfi/revanced-patches#7 (front page and Inbox loaded logged in, login kept
    after `adb install -r`).
  - Step 3: unverified: confirm on the next run.

### Disable ads

- **Changes:** the app's ads-enabled check (`SyncIapHelper`, the method holding `"ADS ENABLED ID: "`) returns false,
  which every ad path reads (SDK set-up, banners, feed and gallery ads, consent form); `MobileAdsInitProvider`'s
  `attachInfo` returns at once, so the Google Mobile Ads SDK never starts.
- **Check:**
  1. Cold start (`adb shell am force-stop "$pkg"`, `adb logcat -c`, then Baseline step 3), open the first post,
     then count ad SDK lines:

     ```bash
     adb logcat -d | grep -ciE 'googleads|doubleclick|googlesyndication|amazon-adsystem|MobileAds'
     ```

     Pass: 0. If it isn't, read the lines before calling it a failure: the pattern has no unpatched baseline.
  2. The thread shows no ad banner (`"$UI" shot thread`). Before the patch it showed a banner rendering as
     "Webpage not available", and Google's consent form over threads.
  3. Optional, needs passwordless `sudo` on the host: capture the device's TLS ClientHellos on the container's
     network interface during the same scenario and list their SNI host names. The device resolves names over
     DNS-over-TLS, so a DNS capture shows nothing useful. Pass: no `*.amazon-adsystem.com`,
     `googleads.g.doubleclick.net`, `pagead2.googlesyndication.com` or `fundingchoicesmessages.google.com`.
     `firebaseremoteconfig.googleapis.com` is the app's remote config, not an ad.
- **Needs:** login, network.
- **Status:**
  - Step 1: unverified: confirm on the next run. edbfi/revanced-patches#9 records no logcat count, and none was
    taken on an unpatched build.
  - Steps 2–3: verified 2026-11-08, edbfi/revanced-patches#9.

### Disable Sync for Lemmy bottom sheet

- **Changes:** removes the one call in `MainActivity.onCreate` that shows the Sync for Lemmy sheet (the sheet class
  holding the button label `"Signup to Sync for Lemmy"`) on every fresh start.
- **Check:**
  1. Cold start: `adb shell am force-stop "$pkg"`, then Baseline step 3, then `"$UI" shot cold-start`. Pass: the
     feed, not a "Sync for Reddit is shutting down" sheet.
  2. `"$UI" dump | grep -c 'Signup to Sync for Lemmy'`. Pass: 0.
- **Needs:** nothing beyond the Baseline.
- **Status:**
  - Step 1: verified 2026-11-08, edbfi/revanced-patches#9.
  - Step 2: unverified: confirm on the next run.

### Enable Sync Ultra

- **Changes:** the app's Ultra check returns true while its purchase check keeps meaning "bought", and every place
  that talks to Sync's servers about Ultra or picks where tags are stored asks the purchase check. Remote Config
  flags are pinned (`c4266fa` and `ultra_restore` off, `ultra_translate` on). The Ultra screen shows the
  subscription card, Settings cloud backup and Reset only after a purchase. The Translate badge URLs point at
  `ap.syncforreddit.com/image?url=`, which the extension fails on the device, and the extension's `WebsitePreviews`
  is switched on, so website previews are read from the linked page's `og:image` on the phone.
- **Check:**
  1. More actions → Settings → **Sync Ultra**. Pass: the screen shows Paint users, Tag users, Website previews (on),
     Translate, Select text and Support, and no subscription card, Settings cloud backup or Reset.
  2. Tag users → add a throwaway tag (for example `revanced-test`) on a public account (#20 used `spez`) through the
     **Add user tag** dialog (**Username**, **Tag**, **Add**). It must be stored locally:

     ```bash
     adb shell "su 0 sh -c 'grep -h -A2 user_tags /data/data/$pkg/shared_prefs/*.xml'"
     ```

     Pass: a `user_tags` set holding the tag. Then remove the tag in the app, and check it is gone.
  3. The tag sheet's menu shows only **Clear all**, which toasts "TODO" (a known issue, not a failure).
  4. Website previews: force-stop the app, clear only the image cache, then open a busy thread with links to sites
     that set `og:image` (#20 used an r/selfhosted megathread with GitHub links):

     ```bash
     adb shell am force-stop "$pkg"
     adb shell "su 0 rm -rf /data/data/$pkg/cache/image_manager_disk_cache"
     adb logcat -c
     ```

     Scroll the comments, then list the previews that failed:

     ```bash
     adb logcat -d | grep -oE 'Load failed for https://ap.syncforreddit.com/image\?url=[^ ]+' | sort -u
     ```

     Pass: inline and long-press previews show for pages with an `og:image`; the failures listed are pages without
     one. Linked sites see the device's address: that is the patch's documented behaviour.
  5. The "Get Sync Ultra" prompts are gone from the drawer and the account picker.
  6. With Website previews turned off in Sync Ultra's settings, previews stay blank and the log shows no preview
     loads for the same thread (clear the image cache first, as in step 4). Turn the setting back on after.
  7. The comment overflow menu shows the Ultra entries the patch unlocks.
- **Needs:** login, network. Translate and Select text need Google Play services (ML Kit), which Redroid lacks:
  they can't be checked on this device; report them as not checked, not as failures.
- **Status:**
  - Steps 1–4: verified 2026-11-09, edbfi/revanced-patches#20.
  - Steps 5–7: unverified: confirm on the next run. #20 could not open the comment overflow menu through adb.

### Fix /s/ links

- **Changes:** the app's link router (`LinkHelper`, the method holding `"Link title: "`) first calls
  `ShareLinks.open`, which resolves `reddit.com/r|u|user/<name>/s/<id>` off the main thread with one GET (4 s
  timeout, the app's Reddit User-Agent), strips `share_id` and `utm_*` from the `Location` target and reopens it
  through `IntentActivity`. On failure it toasts "Could not open the share link".
- **Check:**
  1. With the app running, open a share link from outside it:

     ```bash
     adb logcat -c
     adb shell am start -a android.intent.action.VIEW -d 'https://www.reddit.com/r/chicago/s/UBknncuPg6' -p "$pkg"
     sleep 10
     "$UI" dump | grep -E 'snackbar|Error loading page'
     adb logcat -d | grep -E 'Unexpected response code 404|Could not resolve|FATAL'
     ```

     Pass: the post opens (`"$UI" shot slink`), no "Error loading page: 404" snackbar, no Volley 404 for
     `oauth.reddit.com/r/<sub>/comments/<share id>.json`, no `edbfi` "Could not resolve" warning.
  2. The same from a cold start: `adb shell am force-stop "$pkg"`, then the `am start` above.
  3. Tap a `/s/` link inside the app (in a comment or a self post): the post it points to opens.
- **Needs:** network; a public `/s/` share link (the one above is from #10; if it no longer redirects, use another
  public one).
- **Status:**
  - Steps 1–2: verified 2026-11-08, edbfi/revanced-patches#10.
  - Step 3: unverified: confirm on the next run.

### Fix Redgifs

- **Changes:** the Volley hook answers the app's three Redgifs requests (`api.redgifs.com/v2/oauth/client`, `/info`,
  `/v2/gifs/<id>`) from Redgifs' temporary-token API, with IDs lowercased and the system User-Agent. For Enhanced
  autoplay, both of the app's video sources get a resolver that turns `…image?url=redgifs-<id>` into Redgifs' HD
  video URL.
- **Check:**
  1. Never open the post in the viewer (it plays the video). Instead start the app's download job for a Redgifs
     watch link (`<subreddit>`: the subreddit of the post that links it) and read the log:

     ```bash
     adb logcat -c
     adb shell "su 0 sh -c 'am broadcast -n $pkg/.receiver.download.RetryReceiver --es title RedgifsTest \
       --es subreddit <subreddit> --es url https://www.redgifs.com/watch/<id> --ei mode 1 --ei id 1'"
     sleep 20
     adb logcat -d | grep -iE 'redgifs|Volley|edbfi|Worker result'
     ```

     Pass: the log names `https://media.redgifs.com/<Id>.mp4`; no Volley
     `Unexpected response code 404 for https://api.redgifs.com/info`; no `edbfi` "Redgifs request failed". A Glide
     `Load failed for https://media.redgifs.com/<Id>.mp4` and a failed `DownloadMediaJob` are expected: the job
     loads media as a bitmap and can't save an mp4 (#10). There is no file to inspect for Redgifs.
  2. Enhanced autoplay can only be checked without playing by hooking the running app (#19 used Frida: both video
     sources opened `…?url=redgifs-<Id>` as `https://media.redgifs.com/<Id>.mp4`, other URLs unchanged). That needs
     `adb root` and a frida-server on the shared device: do it only when the owner agrees, then remove frida-server
     from `/data/local/tmp` and run `adb unroot`. Keep Enhanced autoplay off otherwise.
- **Needs:** network; a public Redgifs watch link (#10's Evidence names the one used; Redgifs content is often
  adult, so pick one with care and don't screenshot it).
- **Status:**
  - Step 1: verified 2026-11-08, edbfi/revanced-patches#10.
  - Step 2: verified 2026-11-09, edbfi/revanced-patches#19.

### Fix Tenor previews

- **Changes:** with the image-client hook (an OkHttp interceptor in the client Glide uses), previews the app asks of
  `ap.syncforreddit.com/image?url=<tenor link>` come from Tenor instead: media links load as they are, `/view/`
  pages through Tenor's oEmbed thumbnail, share links (`tenor.com/<x>.gif`) followed to their page.
- **Check:**
  1. Clear the image cache (Enable Sync Ultra, step 4), then open a thread with a `tenor.com/view/…` link in a
     comment or the post, and scroll to it:

     ```bash
     adb logcat -c
     adb shell am start -a android.intent.action.VIEW \
       -d 'https://www.reddit.com/r/RPGMaker/comments/1xger3g/' -p "$pkg"
     ```

     Then `adb logcat -d | grep -E 'image\?url=https?://(www\.)?tenor\.com'`. Pass: the preview shows a thumbnail
     (`"$UI" shot tenor`), and no `Load failed`, `Unauthorized, status code: 401` or "Sync's image server is gone"
     line for the Tenor link.
- **Needs:** network; a thread with a Tenor link (the one above is from #19).
- **Status:** verified 2026-11-09, edbfi/revanced-patches#19.

### Hide Gfycat link previews

- **Changes:** in the app's inline link preview decision, right after its `tenor.com` test, a Gfycat link (the
  app's own Gfycat test) skips the preview, so it stays a plain link.
- **Check:**
  1. Open a thread whose comments link `gfycat.com` or `giant.gfycat.com` (#19 opened one from this search):

     ```bash
     adb logcat -c
     adb shell "am start -a android.intent.action.VIEW \
       -d 'https://www.reddit.com/r/gifs/search?q=gfycat.com&restrict_sr=on&sort=comments&t=all' $pkg"
     ```

     Open a result, scroll its comments, then `adb logcat -d | grep -cE 'image\?url=.*gfycat'`. Pass: 0, and no
     empty preview box under the Gfycat links. Before the patch, Glide logged
     `Load failed for https://ap.syncforreddit.com/image?url=http://giant.gfycat.com/…`.
- **Needs:** network; a thread with Gfycat links in comments.
- **Status:** verified 2026-11-09, edbfi/revanced-patches#19.

### Fix post thumbnails

- **Changes:** right after the app reads a listing's `thumbnail` (`PostThumbnailHelper`), `&amp;` in the URL becomes
  `&`; Reddit answers the escaped URL with 403.
- **Check:**
  1. Open a busy subreddit in a layout that shows thumbnails (#10 used r/worldnews in List view):
     `adb shell am start -a android.intent.action.VIEW -d 'https://www.reddit.com/r/worldnews/' -p "$pkg"`, wait,
     scroll once, `"$UI" shot thumbnails`. Pass: thumbnails fill their slots; titles unchanged.
- **Needs:** network.
- **Status:** verified 2026-11-08, edbfi/revanced-patches#10.

### Fix video downloads

- **Changes:** in the DASH manifest parser (`RedditVideoRequest.parseNetworkResponse`), both audio tests follow
  `Mpd.isAudio`: the AdaptationSet's `contentType`, then `mimeType`, then its Representations' `mimeType`, then the
  old file-name test. v.redd.it now names audio `CMAF_AUDIO_*.mp4`, which the old test read as the video.
- **Check:**
  1. Start the app's download job for a v.redd.it video (no playback):

     ```bash
     adb shell "su 0 sh -c 'rm -f /sdcard/Android/data/$pkg/cache/images/*.mp4'"
     adb logcat -c
     adb shell "su 0 sh -c 'am broadcast -n $pkg/.receiver.download.RetryReceiver --es title VideoTest \
       --es subreddit magpies --es url https://v.redd.it/9t7qu1y5bc0i1 --ei mode 1 --ei id 2'"
     sleep 40
     adb logcat -d | grep -E 'Worker result|DownloadRedditVideoJob|FATAL'
     ```

     `Worker result FAILURE` for `DownloadRedditVideoJob` is expected here: only the copy to shared storage fails.
  2. Pull the merged file into its own directory and inspect its tracks:

     ```bash
     d="$RUN/downloads/video-1"; mkdir -p "$d"
     f=$(adb shell "su 0 sh -c 'ls /sdcard/Android/data/$pkg/cache/images/*.mp4'" | tr -d '\r' | tail -1)
     adb shell "su 0 sh -c 'cat $f'" > "$d/video.mp4"
     ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,duration -of compact \
       "$d/video.mp4"
     ```

     Pass: a video stream (`codec_type=video`, h264 with width and height) and an audio stream (`aac`). Fail: audio
     only (before the patch: one `aac` stream, about 225 KB). Don't open the file in a player.
  3. Remove the cached file: `adb shell "su 0 sh -c 'rm -f /sdcard/Android/data/$pkg/cache/images/*.mp4'"`.
- **Needs:** network, `ffprobe` on the host, root on the device.
- **Status:** verified 2026-11-08, edbfi/revanced-patches#10 (H.264 720×1280 plus AAC, 3.6 MB).

### Fix View more comments

- **Changes:** the Volley hook answers the app's `POST api/morechildren` (403 for this client) from the comment pages
  Reddit still serves: the parent's page for replies, one page per top-level comment (4 at a time, at most 20 per
  tap, the rest as a new "View more" row), flattened in the order the app expects. It never sends the app's own
  request.
- **Check:**
  1. Open a large thread (#11 used AskReddit threads), then find a "View more" row:

     ```bash
     adb logcat -c
     adb shell am start -a android.intent.action.VIEW -d 'https://www.reddit.com/r/AskReddit/comments/<id>/' -p "$pkg"
     "$UI" dump | grep -E 'View more \([0-9]+\)'
     ```

     Scroll until one shows, tap it (`"$UI" tap '^View more'`), wait a few seconds, dump again.
     Pass: the row is replaced by its replies at the right depth (or by fewer replies and a new, smaller row); the
     log has no `Unexpected response code 403` for `api/morechildren`.
  2. `adb logcat -d -s edbfi:W`. "More comments failed" is a failure. "Comment <id> failed" with a Reddit 5xx is a
     live Reddit error: the comment comes back in the new row; tap it again.
  3. Scroll far down a thread of a few thousand comments: the top-level row loads itself as the list scrolls.
- **Needs:** login, network, a thread with "View more" rows (nested and top-level).
- **Status:** verified 2026-11-08, edbfi/revanced-patches#11.

### Fix galleries

- **Changes:** the Volley hook answers the app's gallery request, `oauth.reddit.com/api/info.json?id=t3_<post>`
  (403), from `/comments/<post>.json?limit=1`, after checking the listing holds that post. A failure becomes an
  error the app reports as "Error loading album".
- **Check:**
  1. Open a Reddit gallery post through the app's link handler (the inner quotes keep the device shell from reading
     the `?`):

     ```bash
     adb logcat -c
     adb shell am start -a android.intent.action.VIEW \
       -d "'https://www.reddit.com/r/pics/comments/1xqmxz2?is_gallery=true'" -n "$pkg/.ui.activities.IntentActivity"
     sleep 6
     adb logcat -d | grep -E 'MultiImageActivity|edbfi|Error loading|FATAL'
     "$UI" dump | grep -E '[0-9]+ / [0-9]+'
     ```

     Pass: the log starts `.ui.activities.media.MultiImageActivity`, the viewer shows a page counter such as
     `1 / 3`, and a swipe (`adb shell input swipe 900 1200 150 1200 300`) moves it to the next page. Fail:
     "Error loading album", or an `edbfi` "Gallery request failed".
- **Needs:** login, network, a Reddit gallery post (the one above is from #12; any public gallery will do).
- **Status:** verified 2026-11-08, edbfi/revanced-patches#12.

### Fix Other discussions

- **Changes:** at the start of the posts-URL builder (`OAuthPostsRequest`), the listing key `seen###<link>` becomes
  the app's own search key `search######url:<link>`, so the app runs a Reddit search for the link; the listing
  keeps its "Other discussions" title.
- **Check:**
  1. Open a link post (not a self post), e.g. the r/worldnews post #14 used:

     ```bash
     adb shell am start -a android.intent.action.VIEW -d 'https://www.reddit.com/r/worldnews/comments/1xmyafj/' \
       -p "$pkg"
     ```

  2. `adb logcat -c`, tap **More actions** in the thread's toolbar, then **Other Discussions** in the "Comment
     actions" sheet: `"$UI" tap '^More actions$'`, then `"$UI" tap '^Other Discussions$'` (the raw uiautomator
     text is `Other&#10;Discussions`; ui.sh turns the line break into a space).
  3. `adb logcat -d | grep -E 'Unexpected response code|submit.json'`. Pass: the link's posts in other
     subreddits, no "Error loading page: 403" snackbar and no Volley 403 for
     `www.reddit.com/submit.json?url=…`.
- **Needs:** login, network, a link post that other subreddits also posted.
- **Status:** verified 2026-11-09, edbfi/revanced-patches#14.

### Fix Imgur

- **Changes:** the Volley hook answers the app's Imgur requests from `api.imgur.com/3` with `Client-ID <option>` and
  the system User-Agent: albums and images (via the dead `images.syncforreddit.com` mirror URLs), a `/gallery/`
  single image as an album of one, uploads (from the RapidAPI URL), and the upload switch on
  `raw.githubusercontent.com` (answered locally). The image-client hook turns album previews
  (`image?url=imgur-album-<id>`) into the cover's `i.imgur.com/<id>m.jpg`. Titled links (`/a/<title>-<id>`) keep
  their ID.
- **Check:**
  1. Albums open in the app's viewer:

     ```bash
     adb logcat -c
     for u in https://imgur.com/a/JJ1nIF4 https://imgur.com/gallery/sA0vrp0; do
       adb shell am start -a android.intent.action.VIEW -d "'$u'" -n "$pkg/.ui.activities.IntentActivity"
       sleep 7; "$UI" dump | grep -E '[0-9]+ / [0-9]+'; "$UI" shot "imgur-${u##*/}"
       adb shell input keyevent KEYCODE_BACK; sleep 1
     done
     adb shell dumpsys activity activities | grep -m1 topResumedActivity
     adb logcat -d | grep -E 'edbfi|WebViewActivity|Error loading'
     ```

     Pass: each opens in `MultiImageActivity` with a page counter (the gallery link showed `1 / 6`); no
     "Error loading album, opening in browser", no `WebViewActivity`, no `edbfi` "Imgur request failed".
  2. Album previews: clear the image cache (Enable Sync Ultra, step 4), open a post or thread with an
     `imgur.com/a/<id>` link in its text (#15 used `imgur.com/a/RTQseoT`), then
     `adb logcat -d | grep -E 'imgur-album|status code: 401'`. Pass: the preview shows the album cover; no Glide
     failure for `image?url=imgur-album-<id>`.
  3. Upload, only when the owner allows it for this run and only with a contentless image: an upload publishes the
     image on Imgur, and the run keeps no way to delete it. Make one and put it where the picker sees it:

     ```bash
     magick -size 64x64 xc:'#3a7' "$RUN/edbfi-upload-test.png"
     adb push "$RUN/edbfi-upload-test.png" /sdcard/Pictures/
     adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE \
       -d file:///sdcard/Pictures/edbfi-upload-test.png
     ```

     Open the comment editor on any post, use its image button (`format_image` in a dump) and pick the file. Pass:
     the **Insert image** dialog offers an `https://i.imgur.com/<id>.png` link. Then **Cancel** and leave the
     editor: never send the comment. Delete the file and its media row:

     ```bash
     adb shell rm /sdcard/Pictures/edbfi-upload-test.png
     adb shell content delete --uri content://media/external/images/media \
       --where "\"_display_name='edbfi-upload-test.png'\""
     ```

- **Needs:** login (comment editor), network. A non-default `Imgur client ID` is an option of this patch: check it
  only on a separate build, and only if the owner supplies an ID.
- **Status:**
  - Steps 1 and 3: verified 2026-11-08, edbfi/revanced-patches#12; the upload past the switch again 2026-11-09,
    edbfi/revanced-patches#15.
  - Step 2: verified 2026-11-09, edbfi/revanced-patches#15.

### Use /user/ endpoint

- **Changes:** rewrites the six `u/` and `https://oauth.reddit.com/u/` literals in the user-profile requests
  (`OAuthUser*`, `OAuthSubredditInfo`, `OAuthFriend`/`OAuthUnfriend`, the methods holding `/about.json`) to
  `user/`, cache keys included.
- **Check:**
  1. The docs list this patch as off by default, so check it only on a build with the patch enabled explicitly
     (CLI `-e "Use /user/ endpoint"`; the repo's patch command
     passes extra CLI arguments through, see its Commands). Run the Baseline on that build.
  2. Open a public profile:
     `adb shell am start -a android.intent.action.VIEW -d 'https://www.reddit.com/user/spez' -p "$pkg"`, then
     `"$UI" dump | grep -E 'karma'`. Pass: the profile loads with its karma line and section chips; no Volley
     error in the log.
  3. Afterwards reinstall the default build with `adb install -r`, so the device is back on the default selection.
- **Needs:** network; a build with `-e`. Without the patch the profile loads too (Reddit redirects `/u/` to
  `/user/`), so this check only shows the patch does no harm; there is no log line that shows which path was asked.
- **Status:** verified 2026-11-08, edbfi/revanced-patches#10.

## Checks that need two builds

- **Before and after.** Every PR above compared the patched build with a build of the earlier patches only (CLI
  `-d "<patch>"` for the patch under test). Use that when a check's "pass" is only clear against the old behaviour;
  install both with `adb install -r`, and end on the build that should stay installed.
- **CLI build against Manager's Save APK build.** Per-patch effects don't depend on how the APK was patched: Manager
  adds only "same output". Run the full checklist on one build, and on the other run the Baseline plus a few checks
  that cover the extension (for example Fix galleries and Fix Tenor previews), after the provenance checks in
  [apk-provenance.md](../apk-provenance.md). Manager's default mixed selection (with ReVanced Patches' own Sync
  patches) is a different app: see [manager.md](../manager.md) and [host-checks.md](../host-checks.md).
- **Default and off-by-default.** Use /user/ endpoint needs its own `-e` build (above).

## Known issues

Read the Known issues section of the patches repo's `docs/syncforreddit.md` before reporting a failure. A symptom it
lists (for example Clear all only saying "TODO", Translate needing Play services, "Other discussions" missing a post)
is expected; report it as a known issue, not as a failure. A symptom it doesn't list is a finding.

## Unverified

Patches with at least one check marked `unverified: confirm on the next run`:

- Spoof client (step 3)
- Disable ads (step 1)
- Disable Sync for Lemmy bottom sheet (step 2)
- Enable Sync Ultra (steps 5–7)
- Fix /s/ links (step 3)
