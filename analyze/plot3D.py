import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.cm as cm

results = np.load("./results.npz")["results"]
# results[results != -1] = 1 - results[results != -1]  # Invert win rates
player_range = range(5, 21)

# Create a mask for the -1 values
mask = results == -1

# Transpose results and mask for rotated plot
results_T = results.T
mask_T = mask.T

# Get the colormap and set the color for masked values
cmap = matplotlib.colormaps["YlGnBu"]
cmap.set_bad(color='black')

# --- Start of 3D Plot Code ---

fig_3d = plt.figure(figsize=(12, 8))
ax_3d = fig_3d.add_subplot(111, projection='3d')

# Number of players (x-axis) and number of mafia (y-axis)
num_players_vals = np.array(player_range)
num_mafia_vals = np.arange(1, results.shape[1] + 1)

# Create meshgrid for plotting positions
_x, _y = np.meshgrid(num_players_vals, num_mafia_vals)
xpos, ypos = _x.ravel(), _y.ravel()

# Bar dimensions (centered on integer coordinates)
dx = 0.5  # Width of bars in x direction
dy = 0.5  # Width of bars in y direction
xpos = xpos - dx / 2  # Center bars on x coordinate
ypos = ypos - dy / 2  # Center bars on y coordinate

# Bar height (Mafia win rate)
zpos = np.zeros_like(xpos, dtype=float)  # Bars start from z=0
dz = results.T.ravel()  # Use transposed results to match heatmap orientation

# Filter out masked values (-1)
valid_indices = dz != -1
xpos = xpos[valid_indices]
ypos = ypos[valid_indices]
zpos = zpos[valid_indices]
dz = dz[valid_indices]

# Get colors from the colormap based on height (win rate)
norm = plt.Normalize(0, 1)  # Normalize win rates (0 to 1)
colors = cmap(norm(dz))

# Plot the 3D bars
ax_3d.bar3d(xpos, ypos, zpos, dx, dy, dz, color=colors, zsort='average')

# Set labels and title
ax_3d.set_xlabel('Number of Players')
ax_3d.set_ylabel('Number of Mafia Players')
ax_3d.set_zlabel('Mafia Win Rate')
ax_3d.set_title('3D View of Mafia Win Rate')

# Set ticks to match heatmap
ax_3d.set_xticks(num_players_vals)
ax_3d.set_yticks(num_mafia_vals)
ax_3d.set_xticklabels([str(i) for i in player_range])
ax_3d.set_yticklabels([str(i) for i in range(1, results.shape[1] + 1)])

# Add a color bar
mappable = cm.ScalarMappable(cmap=cmap, norm=norm)
mappable.set_array(dz)
fig_3d.colorbar(mappable, shrink=0.5, aspect=5, label='Mafia Win Rate', cax=fig_3d.add_axes([0.92, 0.15, 0.03, 0.7]))

# plt.tight_layout()
plt.show()