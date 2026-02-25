# Skill Rating Setup - CRITICAL NEXT STEP

## ⚠️ Important: You Must Run This Command

The Skill Rating columns are now showing in the tables, but they will display **0.00** until you populate the values.

## How to Populate Skill Ratings

### Option 1: Railway CLI (Recommended)
```bash
railway run python manage.py recalculate_skill_ratings
```

### Option 2: Railway Dashboard
1. Go to Railway Dashboard
2. Click on your project
3. Click "Shell" tab
4. Run: `python manage.py recalculate_skill_ratings`

### Option 3: Add as Pre-deploy Command Temporarily
1. Go to Railway Dashboard → Settings → Deploy
2. Set Pre-deploy Command to: `python manage.py recalculate_skill_ratings`
3. Trigger a new deployment (or just run the command in shell instead)
4. **IMPORTANT:** Remove the Pre-deploy Command after running once

## What This Command Does
- Calculates skill rating for all 157 PlayerSeasonStats records
- Uses **NEW weighted formula** combining match rating and contribution scoring
- Sorted by skill_rating (higher = better overall performance)

## How Skill Rating Works (NEW FORMULA)

### Weighted Components:
- **Match Rating (80%)** - Your average match performance rating (PRIMARY FACTOR)
- **Contribution Score (20%)** - Position-based scoring for goals, assists, clean sheets

### Contribution Points by Position:

**Attackers (ST, LW, RW):**
- Goal = 5 points
- Assist = 3 points
- Max 15 points per match

**Midfielders (CAM, CM):**
- Goal = 5 points
- Assist = 3 points
- Max 12 points per match

**Defenders (LB, CB, RB):**
- Goal = 6 points (rare, high value!)
- Assist = 5 points
- Clean Sheet = 3 points
- Max 10 points per match

**Goalkeepers (GK):**
- Clean Sheet = 3 points
- Max 8 points per match

**Others (CDM, etc.):**
- Goal = 5 points
- Assist = 3 points
- Clean Sheet = 2 points
- Max 12 points per match

### Final Formula:
```
Contribution Score = Total Contribution Points / Matches Played
Skill Rating = (0.8 × Avg Match Rating) + (0.2 × Contribution Score)
```

### Examples:
**Attacker with 8.5 rating, 10 goals, 5 assists in 10 games:**
- Match Rating Component: 0.8 × 8.5 = 6.80
- Contribution Points: (10×5 + 5×3) / 10 = 6.5
- Contribution Component: 0.2 × 6.5 = 1.30
- **Skill Rating: 8.10**

**Defender with 7.5 rating, 1 goal, 2 assists, 6 clean sheets in 10 games:**
- Match Rating Component: 0.8 × 7.5 = 6.00
- Contribution Points: (1×6 + 2×5 + 6×3) / 10 = 3.4
- Contribution Component: 0.2 × 3.4 = 0.68
- **Skill Rating: 6.68**

**Goalkeeper with 8.0 rating, 8 clean sheets in 10 games:**
- Match Rating Component: 0.8 × 8.0 = 6.40
- Contribution Points: (8×3) / 10 = 2.4
- Contribution Component: 0.2 × 2.4 = 0.48
- **Skill Rating: 6.88**

## Why This System is Better
✅ **Match rating is king (80%)** - performance is the PRIMARY factor  
✅ **Rewards contributions (20%)** - goals, assists, clean sheets still count  
✅ **Position-balanced** - defenders get more points for goals (harder to score)  
✅ **Anti-stat padding** - per-match caps prevent one big game from skewing stats  
✅ **Fair to all roles** - goalkeepers and defenders valued for their contributions  

## After Running Command
✅ Rankings page will show skill ratings (sorted highest to lowest)  
✅ Overview page will show skill ratings for top players  
✅ Future stats will auto-calculate on save  
✅ TOTW feature will use skill ratings for selection
