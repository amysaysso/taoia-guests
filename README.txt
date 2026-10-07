THE ART OF IMPERFECT ADULTING - GUEST DIRECTORY SETUP GUIDE
===========================================================

This turns the guest Google Sheet into a single web page that search
engines and AI tools can read. Every morning it reads the Sheet, rebuilds
the page, and publishes it. You only ever edit the Sheet.

It works exactly like the UNMUTED directory, and uses the same GitHub
account. This one gets its own repository.


WHAT'S IN THE FOLDER
--------------------
generate.py   Reads the Sheet and writes the page.
build.yml     Runs generate.py every morning and publishes the result.


HOW THE SHEET IS USED
---------------------
Shown on the page:

  Guest Name
      Card heading. Rows without a Guest Name or Episode Title are skipped.

  Episode Title
      Shown under the name, linked to the article.

  Link to Episode Article
      The "Read the story" link.

  YouTube Link
      The "Watch on YouTube" link, plus the video thumbnail on the card.
      Regular, short (youtu.be) and Shorts links all work.

  Guest Website Addy
      The "Visit [first name]'s website" link. Shown ONLY when Backlink Y/N
      is Y. A full link or just the domain (example.com) both work.

Used behind the scenes, never shown and never written into the page:

  Release Date and Episode #
      Used only to put the newest guests first.

  Backlink Y/N
      Decides whether the guest's website link appears.

Ignored completely:

  Category


ONE-TIME SETUP (ABOUT 20 MINUTES)
---------------------------------

STEP 1. Publish the Sheet as CSV

  In Google Sheets, go to File > Share > Publish to web.
  Choose the guest tab (not "Entire document").
  Choose "Comma-separated values (.csv)" and click Publish.
  Copy the link it gives you.

  Note: the published CSV itself is public, even though the page hides
  Release Date, Episode #, Category and Backlink Y/N. Someone who found
  the CSV link could see those columns. If that matters, make a second
  tab that pulls in only Guest Name, Episode Title, the three links and
  Backlink Y/N, and publish that tab instead.


STEP 2. Create the GitHub repository

  1. In GitHub, create a new repository, for example "taoia-guests".
  2. Click Add file > Upload files, and upload generate.py and this guide.
  3. Add the schedule file by hand:
       - Click Add file > Create new file.
       - For the file name, type exactly:  .github/workflows/build.yml
       - Open build.yml on your computer, copy everything in it, and
         paste it into the big box.
       - Click "Commit changes".


STEP 3. Add the settings

  In the repository, go to Settings > Secrets and variables > Actions.

  On the "Secrets" tab, click "New repository secret":
      Name:   SHEET_CSV_URL
      Value:  the link from Step 1

  On the "Variables" tab, click "New repository variable" twice:
      Name:   SITE_URL
      Value:  https://guests.amysaysso.com

      Name:   CUSTOM_DOMAIN
      Value:  guests.amysaysso.com


STEP 4. Turn on publishing

  Go to Settings > Pages.
  Under "Source", choose "GitHub Actions".
  Under "Custom domain", enter: guests.amysaysso.com


STEP 5. Point the subdomain

  Wherever the DNS for amysaysso.com is managed, add a CNAME record:

      Name / Host:    guests
      Value / Target: YOUR-GITHUB-USERNAME.github.io

  Once it works (can take a few hours), go back to Settings > Pages and
  tick "Enforce HTTPS".


STEP 6. Run it once

  Go to the Actions tab, choose "Build and publish guest directory", and
  click "Run workflow". After that it runs on its own every morning.


WHEN THE ARTICLES MOVE TO AMYSAYSSO.COM
---------------------------------------
You don't need to edit the Sheet. Add two more variables (Step 3):

      Name:   OLD_ARTICLE_BASE
      Value:  https://www.imperfectadulting.com

      Name:   NEW_ARTICLE_BASE
      Value:  the new address of the articles, for example
              https://amysaysso.com/imperfectadulting

From the next run, every article link on the page points to the new
address. It works whether the Sheet's links have "www" or not.


EVERYDAY USE
------------
- Add a row to the Sheet when an episode is published. The page updates
  the next morning.
- Need it sooner? Actions > Build and publish guest directory >
  Run workflow.
- To link to one guest, add their anchor to the address, for example:
      https://guests.amysaysso.com/#devon-adrienne
  The anchor is the guest's name in lowercase with dashes.


AFTER LAUNCH
------------
- Add the sitemap in Google Search Console:
      https://guests.amysaysso.com/sitemap.xml
- Redirect the old guest directory page on imperfectadulting.com to the
  new address.
- Link to the guest directory from the TAOIA section of amysaysso.com
  and from your YouTube channel's "About" links.
