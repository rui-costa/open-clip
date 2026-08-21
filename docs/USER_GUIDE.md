# User Guide

This guide walks you through the core workflow of using OpenClip to process and manage video clips.

## 1. Getting Started: Projects Page
When you launch the application, you arrive at the **Projects Page**. This is your dashboard for all video processing tasks.

![Projects Page](../images/projects_page.png)

From here, you can view existing projects or create a new one.

## 2. Uploading a Video
To start a new project, click the upload button to navigate to the **Upload Screen**.

![Upload Screen](../images/upload_screen.png)

1. Select your video file.
2. Provide necessary project details.
3. Upon submission, the project is created, and you are automatically navigated to the **Project Details** page.

## 3. Running the Pipeline and Managing Details
In the **Project Details** view, the project is initialized but not yet processed.

![Project Details](../images/project_details.png)

1. **Trigger Processing**: Click the action to start the pipeline. The interface is reactive and will update in real-time as the backend processes the video.
2. **Review Output**: Once complete, you can view the transcription, manage generated clips, and perform clip-specific actions.
3. **Publish one clip**: **Upload to YouTube** on a clip's detail page publishes that clip on its own, with the title and description described below. The clip is cut again first, from its settings as they stand — so the Clips step is not something to run beforehand, and what goes up is what the page was showing rather than a file cut before the last change to its captions or title. That makes it an encode followed by an upload: the button reports that it is running and keeps going if you leave the page, and the published link appears on the clip when it lands. A clip that is already live says so instead of offering an untouched button, and uploading a second time adds another video rather than replacing the first.
4. **Work from the grid**: every action on a clip's detail page is also on its card in the grid — upload, re-render, captions, overlay text and thumbnail — so a pass over a dozen clips does not mean opening a dozen pages. The card guards publishing the same way the detail page does, and a card whose clip is already live links to the video and to its Studio page.

## 4. Captions and Animated Subtitles
The **Captions** panel sits in the right-hand column of the project page, and again on any clip's detail page beside its preview player. Captions are a project setting either way — the renderer burns the same style into every clip — so setting them from the project page decides it before anything is cut.

1. **Pick a preset**: *Karaoke Pop* (a few words on screen, the spoken one lights up and pops), *Word Punch* (one oversized word at a time), *Boxed Bold* (karaoke on a solid block), or *Clean Lines* (plain, unanimated subtitle blocks).
2. **Adjust it**: size, position on the frame, width, how many words share the screen, outline thickness, emphasis on the spoken word, and the text, spoken-word and outline colours. Sliders are sized as percentages of the frame, so the same settings hold at any output resolution.
3. **Watch the preview**: play the clip and the captions animate over it, word by word. This is drawn from the same cues and style the renderer uses, so it is what the burned clip will look like, not an approximation.
4. **Render**: with **Burn captions into rendered clips** ticked, running the **Clips** step burns them into each clip. An `.ass` subtitle file is written next to every clip either way, so the captions can also be dropped straight into an editor.

Captions come from the word-level timings the **Transcript** step already produces, so there is no extra transcription pass and no cost to changing the style.

Caption settings belong to the project. The **Settings Page** only sets where a *new* project starts; restyling one project never touches another. Changing the style of a clip that is already rendered needs the **Clips** step re-run to reach the file.

One clip can break away from the project's style with the padlock button on its card. The dialog that opens plays the clip itself with the captions drawn over it, so placement — whether the words clear a face, a lower third, or the platform's own controls — is judged against the footage they will land on rather than against a slider labelled "% from top". **Use custom settings** copies the project's current values onto the clip as a starting point, so unlocking changes nothing by itself; **Follow the project again** discards the clip's copy. A clip whose cut file already has captions burned in is previewed from the source instead, because drawing over burned words would show two sets at once.

> Burning captions in needs an ffmpeg built with libass. The Docker image has one. A local ffmpeg without it still cuts clips and still writes the `.ass` files, but the pixels come out uncaptioned — check with `ffmpeg -filters | grep subtitles`.

## 5. Overlay Titles
A clip can carry a title of its own: one piece of text drawn over the picture at the start of the clip and faded out a few seconds later. Unlike captions, this belongs to the single clip you are looking at, so it is edited from that clip's detail page with **Add overlay text**.

1. **Write it**: the text is saved as you type, and drawn over the player behind the dialog as you go. A line break in the box is a line break on the video.
2. **Time it**: the title starts at the top of the clip by default and stays for three seconds. **Starts at**, **Stays for** and **Fades out over** move all of that; playing the clip shows the real timing, including the fade.
3. **Style it**: size, position from the top of the frame, width, outline, colours, uppercase and a background block. Like the caption sliders these are percentages of the frame, so they hold at any output resolution.
4. **Burn it in**: the title is drawn over the preview immediately, but it only reaches the file when the clip is cut. Use **Regenerate clip** on the same page.

**Remove this title** at the foot of the dialog takes it off the clip entirely; re-cutting then produces a clip without it.

### Regenerating a single clip
**Regenerate clip** re-cuts the one clip you are looking at with whatever its settings now say — its title, its captions, and the project's aspect ratio and resolution. Every other rendered clip is left alone, which is the difference between this and re-running the **Clips** step, and it is also how a clip that has never been cut gets rendered on its own.

The encode runs on the backend and keeps going if you leave the page. The button reports when it finishes, and says so plainly if the render stopped without producing a file.

## 6. Thumbnails
Every clip has a thumbnail without being asked for one: the first frame of the clip, with the clip's title drawn on it and no subtitles. If that is the thumbnail you want, there is nothing to do.

No picture file is made in advance. A thumbnail is a frame of the clip with text over it, and the app draws both — so what you see on the clip page and on every card *is* the thumbnail, live, updating the moment you change it. The image itself is rendered once, at upload, and attached to the video.

The title on it is worked out rather than typed. It is the clip's own overlay text; a clip that has none uses the hook the model wrote for that moment, then the YouTube title. Editing the overlay text therefore changes the thumbnail too, which is the point: the picture and the opening seconds of the video should not say different things.

**Edit thumbnail** on the clip's detail page changes the two decisions a machine cannot make:

1. **Which frame**: scrub the player at the top of the dialog to the frame you want and press **Use the frame showing now**. A frame past the end of the clip is pulled back inside it, because the source keeps going where the clip does not.
2. **What is written on it**: the clip's title can be switched off, the subtitles can be switched on — only the line being spoken on the chosen frame is drawn — and **Extra text** adds a second line that appears on the picture and never on the video. It gets its own size, position and width, in percentages of the frame like every other text control here.

**Back to defaults** returns the clip to the first frame with its title on it. **Make the thumbnail** is there when you want the file itself — to download it, or to check it against the preview. It is burned by the renderer that cuts the clips, at the project's aspect ratio and with the fonts the burn uses, so it is the frame rather than an impression of it. You never have to press it: uploading renders the picture from the same settings.

A clip that is sitting still shows its thumbnail rather than whichever frame the player happens to be parked on — on the clip's own page and on every card in the grid. It opens on the frame the thumbnail is taken from, so the still is not one moment wearing another moment's title. Pressing play, or scrubbing anywhere, hands the picture back to the video. **Still clips show** in the project's options bar switches the whole project between **Thumbnail** and **Video frame**, which is the one to pick while cutting rather than reviewing. The caption, overlay and thumbnail dialogs always show the footage: their previews exist to show a paused frame.

> A custom thumbnail is attached after the upload, through a separate YouTube call, and a channel without a verified phone number cannot have custom thumbnails at all. If YouTube refuses it, the clip is still published — the picture is what is missing, and it can be set by hand in Studio.

> The file sent is the one in the project's `thumbnails/` folder — the picture you made and can look at. Change it after the clip has gone up and **Upload thumbnail to YouTube**, on the clip's page under Actions, puts the new one on the video that is already there: same video, same id, same views, only the still changes. It is also how a clip published by an older version gets its picture.

> YouTube goes on processing a video after the upload itself has finished, and finishing that processing writes YouTube's own generated thumbnail over anything set in the meantime. So the picture is attached twice: once straight away, and again once YouTube says it is done, which is the one that stays. Asking whether it is done needs the **youtube.readonly** permission — **Settings → YouTube Channel** says when the connected channel is short of it, and **Reconnect Channel** grants it. Without it the second attempt is made on a timer instead, and may land too early.

## 7. YouTube Descriptions
Every clip is uploaded with a description assembled from four sources: what the model wrote about that clip, the original video this project was cut from, text belonging to this project, and text you keep on every project.

The **Description** panel in the right-hand column of the project page holds the project's share of it:

1. **Original video URL**: the full episode the shorts came from. Putting this link in a short's description is how YouTube connects the short back to the video it was cut from, so fill it in before uploading anything.
2. **Original video title**: how the episode is named in prose — the default description reads *"This is a short from the original podcast &lt;title&gt;."*
3. **Project text**: a call to action, links or credits that belong to this project alone.
4. **Template for this project**: overrides the application-wide template, for this project only.

The template is plain text. Anything you type is used exactly as written; a field in braces is replaced with its value. Writing `{highlights.ai_video_description}` gives the description the model wrote for that clip, and writing `this is a text` gives `this is a text`. The **Available fields** list under each template box names every field, `{project.source_url}` and `{global.text}` among them.

A line whose fields are all empty is left out, so a project with no original video URL simply has no link line rather than a dangling label.

**Settings Page → YouTube Descriptions** holds the two application-wide pieces: the text placed wherever the template says `{global.text}`, and the default template every project uses until it overrides it. Unlike the caption defaults, these are read at upload time — editing them changes what every existing project publishes.

Each clip's detail page shows the finished description under **YouTube description**. It is rendered by the same builder the uploader uses, so it is the exact text that gets published.

## 8. Configuring Settings
You can customize the application's behavior in the **Settings Page**.

![Settings Page](../images/settings_page.png)

Adjust your configuration (API keys, models, etc.). Changes made here are saved directly to the backend `settings.json` file.

### Connecting a YouTube channel
Publishing needs two separate things. **YouTube Client Secrets (JSON)** is the OAuth client for your own Google Cloud project — which application is asking. **YouTube Channel → Connect Channel** is the channel's consent — who it may act for. The button opens Google in a new tab; when you finish there, the panel says the channel is connected and the token is written to `backend/youtube_credentials/`.

Nothing about that tab is binding. Close it, pick the wrong account, or walk away: press the button again and another window opens. Attempts do not queue or block each other — whichever one you finish is the one that counts, and any you abandon expire after five minutes. **Cancel** clears them without opening another.

The panel also names any permission the stored connection is short of. That happens to a channel connected before a permission was added to the app: uploads carry on working, and **Reconnect Channel** grants the rest without touching anything else.
