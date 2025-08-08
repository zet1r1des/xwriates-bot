import discord
from discord.ui import View, Button
from discord.ext import tasks
import os

TOKEN = os.getenv(TOKEN)
APPLICATION_CHANNEL_ID = 1354044535507779607  # Replace with your channel ID
APPROVED_ROLE_ID = 1401720174847197204  # Replace with your approved role ID
DECLINED_ROLE_ID = 1354047703314731038  # Replace with your declined role ID

bot = discord.Bot(intents=discord.Intents.all())    

class ApplicationSystem:
    """Central class to manage application state and denied users"""
    _denied_users = set()
    _is_locked = False

    @classmethod
    def add_denied_user(cls, user_id):
        cls._denied_users.add(user_id)

    @classmethod
    def is_user_denied(cls, user_id):
        return user_id in cls._denied_users

    @classmethod
    def lock_applications(cls):
        cls._is_locked = True

    @classmethod
    def unlock_applications(cls):
        cls._is_locked = False

    @classmethod
    def applications_locked(cls):
        return cls._is_locked

    @classmethod
    def reset_denied_users(cls):
        cls._denied_users.clear()


@bot.slash_command(description="Send a message as an embed with optional image")
@discord.default_permissions(administrator=True)  # Restrict to users with admin permissions
async def say(ctx, text: str = None, image: discord.Attachment = None):
    """Command to send a message in an embed with text and an optional image"""

    # Check if the user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You do not have permission to use this command.", ephemeral=True)
        return

    # Create the embed
    embed = discord.Embed(title=ctx.guild.name, color=discord.Color.blue())

    # Add text to the embed if provided
    if text:
        embed.description = text

    # Add image to the embed if provided
    if image:
        embed.set_image(url=image.url)

    # Set the thumbnail to the server's profile picture
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

    # Send the embed in the same channel
    await ctx.send(embed=embed)


class ApplicationReviewView(View):
    """View for staff to review applications"""

    def __init__(self, applicant_id):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    async def update_application_status(self, interaction, status, color, staff_member):
        embed = interaction.message.embeds[0]
        description = embed.description
        description_lines = description.split("\n")
        updated_description = "\n".join(description_lines[:-3])
        updated_description += f"\n## Status: {status}\n"
        updated_description += f"## Reviewed By: {staff_member}\n"

        # Fetch the user by self.applicant_id
        applicant_user = await interaction.client.fetch_user(self.applicant_id)
        updated_description += f"## Applicant: {applicant_user.name} (<@{self.applicant_id}>)\n"

        embed.description = updated_description.strip()
        embed.color = color
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_button")
    async def approve_callback(self, button, interaction):
        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)
        approved_role = guild.get_role(APPROVED_ROLE_ID)

        try:
            await applicant.add_roles(approved_role)
            await self.update_application_status(interaction, "Approved", discord.Color.green(), interaction.user)
            await applicant.send(embed=discord.Embed(title="🎉 Your application has been approved!", description="**Schedule your interview** https://discord.com/channels/1327852872767111211/1401720336374042827", color=discord.Color.green()))
        except Exception as e:
            await interaction.response.send_message(f"Failed to approve: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_button")
    async def decline_callback(self, button, interaction):
        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)
        declined_role = guild.get_role(DECLINED_ROLE_ID)

        try:
            ApplicationSystem.add_denied_user(self.applicant_id)
            await applicant.add_roles(declined_role)
            await self.update_application_status(interaction, "Permanently Declined", discord.Color.red(), interaction.user)
            await applicant.send(embed=discord.Embed(title="❌ Your application has been permanently declined.", description="You will not be able to submit another application, until reset.", color=discord.Color.red()))
        except Exception as e:
            await interaction.response.send_message(f"Failed to decline: {str(e)}", ephemeral=True)


class ApplicationButtonView(View):
    """Main application button that users click to start"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="𝗫𝘄𝗿𝗶𝗮𝘁𝗲𝘀 Applications", style=discord.ButtonStyle.blurple, emoji="<:VIPTicket:1401719870009249943>", custom_id="apply_button")
    async def application_callback(self, button, interaction):
        if ApplicationSystem.is_user_denied(interaction.user.id):
            await interaction.response.send_message("❌ You have been permanently declined.", ephemeral=True)
            return

        if ApplicationSystem.applications_locked():
            await interaction.response.send_message("❌ Applications are currently off.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Check your DMs", ephemeral=True)
        await self.start_application(interaction.user)

    async def start_application(self, user):
        questions = [
            "1. Πόσο χρονών είσαι (15+)",
            "2. STEILE screen | Πόσες ώρες έχεις FiveM (800+)",
            "3. Έχεις τρόπο να κάνεις clip (Nvidia ή AMD)",
            "4. STEILE an | Έχεις pvp highlights ή pvp clips (Must)",
            "5. Έχεις items ? (Must)"
        ]

        answers = []

        for i, question in enumerate(questions):
            embed = discord.Embed(title=question, color=discord.Color.blue())
            await user.send(embed=embed)

            while True:  # Loop until a valid response is received
                try:
                    def check(m):
                        return m.author == user and isinstance(m.channel, discord.DMChannel)

                    response = await bot.wait_for('message', check=check)

                    # Check if it's the second question
                    if i == 1:
                        if not response.attachments:
                            await user.send("❌ You need to send an image with your total hours.")
                            continue  # Ask the same question again
                        else:
                            image_links = ""
                            for attachment in response.attachments:
                                if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                                    if image_links:
                                        image_links += " • "
                                    image_links += f"[Image]({attachment.url})"
                            answers.append(image_links)  # Store the image links
                            break  # Exit the loop after valid response
                    else:
                        answer_text = response.content or "(No text answer)"
                        answers.append(answer_text)
                        break  # Exit the loop for non-image questions

                except discord.Forbidden:
                    await user.send("I cannot send you DMs. Please enable DMs for this server.")
                    return
                except Exception as e:
                    await user.send(f"An error occurred: {str(e)}")
                    return

        # Continue with the rest of the application logic...
        channel = bot.get_channel(APPLICATION_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="New Application", color=discord.Color.blue())
            description = ""
            for question, answer in zip(questions, answers):
                description += f"## {question}\n{answer or 'No response'}\n\n"
            description += "## Status: Pending\n"
            description += "## Reviewed By: Not reviewed yet\n"
            description += f"## Applicant: {user.name} (<@{user.id}>)\n"
            embed.description = description.strip()
            embed.set_author(name=bot.user.name, icon_url=bot.user.display_avatar.url)
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=f"User  ID: {user.id}")

            view = ApplicationReviewView(user.id)
            await channel.send(embed=embed, view=view)

            await user.send(
                embed=discord.Embed(title="✅ Your application has been submitted!", color=discord.Color.green()))
        else:
            await user.send(embed=discord.Embed(title="⚠️ Error submitting application",
                                                description="Please notify developer about this issue",
                                                color=discord.Color.red()))


@bot.slash_command(description="Create an application post")
@discord.default_permissions(manage_messages=True)
async def applications(ctx):
    """Command to create the application message"""
    embed = discord.Embed(
        title=":crossed_swords: 𝗫𝘄𝗿𝗶𝗮𝘁𝗲𝘀 Applications :crossed_swords:",
        description="To start the application press the following button",
        color=discord.Color.blurple()
    )
    embed.set_author(name="𝗫𝘄𝗿𝗶𝗮𝘁𝗲𝘀", icon_url=ctx.bot.user.display_avatar.url)
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1401844619490230282/1402199264502874183/perry-the-platypus-hat-ezgif.com-resize.gif?ex=68930b54&is=6891b9d4&hm=695d03179a837ea30e1d4f9ab1cf447c5949e4cf2f27f95c58469080e3d87653&")
    embed.set_footer(text="𝗫𝘄𝗿𝗶𝗮𝘁𝗲𝘀", icon_url=ctx.bot.user.display_avatar.url)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1388200096180601038/1402727885051138179/20250727172054_1.jpg?ex=6894f7a5&is=6893a625&hm=0decdc503a8dd5d5f5b96c41a3d95bc101de812299731d4d0752d5f44e5dc61e&")

    await ctx.send(embed=embed, view=ApplicationButtonView())


@bot.slash_command(description="Lock applications (developers only)")
@discord.default_permissions(manage_messages=True)
async def lock_applications(ctx):
    """Command to lock applications"""
    if ApplicationSystem.applications_locked():
        await ctx.respond(embed=discord.Embed(title="⚠️ Applications are already locked.", color=discord.Color.blue()), ephemeral=True)
    else:
        ApplicationSystem.lock_applications()
        embed = discord.Embed(title="🔒 Applications are now off.", color=discord.Color.red())
        embed.set_author(name="𝗫𝘄𝗿𝗶𝗮𝘁𝗲𝘀", icon_url=ctx.bot.user.display_avatar.url)
        await ctx.send(embed=embed)


@bot.slash_command(description="Unlock applications (developers only)")
@discord.default_permissions(manage_messages=True)
async def unlock_applications(ctx):
    """Command to unlock applications"""
    if not ApplicationSystem.applications_locked():
        await ctx.respond(ephemeral=True, embed=discord.Embed(title="⚠️ Applications are already open.", color=discord.Color.blue()))
    else:
        ApplicationSystem.unlock_applications()
        embed = discord.Embed(title="🔓 Applications are now open.", color=discord.Color.green())
        embed.set_author(name="𝗫𝘄𝗿𝗶𝗮𝘁𝗲𝘀", icon_url=ctx.bot.user.display_avatar.url)
        await ctx.send(embed=embed)


@bot.slash_command(description="Reset denied users and remove denied role (developers only)")
@discord.default_permissions(manage_roles=True)
async def reset(ctx):
    """Command to reset the denied status of all users and remove the denied role"""
    denied_role = ctx.guild.get_role(DECLINED_ROLE_ID)
    if denied_role is None:
        await ctx.respond("❌ Declined role not found.", ephemeral=True)
        return

    for member in ctx.guild.members:
        if ApplicationSystem.is_user_denied(member.id):
            try:
                await member.remove_roles(denied_role)
            except Exception as e:
                print(f"Failed to remove role from {member.name}: {str(e)}")

    ApplicationSystem.reset_denied_users()
    await ctx.respond("✅ All users have been reset from permanent denial status and denied roles have been removed.", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Adding persistent views
    bot.add_view(ApplicationButtonView())
    # Start background tasks
    update_status.start()
    update_embeds.start()
    update_channels.start()
    update_members_boosts.start()
    update_date.start()
    reset_counts.start()


@tasks.loop(seconds=60)
async def update_status():
    # Your logic to update status
    pass


@tasks.loop(seconds=1)
async def update_embeds():
    # Your logic to update embeds
    pass


@tasks.loop(seconds=60)
async def update_channels():
    # Your logic to update channels
    pass


@tasks.loop(seconds=60)
async def update_members_boosts():
    # Your logic to update member boosts
    pass


@tasks.loop(seconds=60)
async def update_date():
    # Your logic to update date
    pass


@tasks.loop(seconds=60)
async def reset_counts():
    # Your logic to reset counts
    pass


bot.run(TOKEN)

