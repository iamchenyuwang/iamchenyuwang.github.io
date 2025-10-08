# Chenyu Wang - Personal Website

A modern, professional personal website showcasing research, publications, and blog posts.

## 🌟 Features

- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile devices
- **Modern UI/UX**: Clean and professional interface with smooth animations
- **Three Main Sections**:
  - **Home**: Personal introduction and research interests
  - **Publications**: Complete list of academic papers with citation metrics
  - **Blog**: Platform for sharing insights and thoughts

## 🚀 Quick Start

1. Clone this repository
2. Open `index.html` in your web browser
3. That's it! No build process required.

## 📁 File Structure

```
├── index.html          # Homepage
├── publications.html   # Publications list
├── blog.html          # Blog page
├── styles.css         # All styling
├── script.js          # Interactive features
└── README.md          # This file
```

## 🛠️ Customization

### Adding Your Photo

Replace the profile placeholder in `index.html`:
```html
<div class="profile-placeholder">
    <i class="fas fa-user"></i>
</div>
```

With:
```html
<img src="your-photo.jpg" alt="Chenyu Wang" style="width: 300px; height: 300px; border-radius: 50%; object-fit: cover;">
```

### Updating Publications

Edit the publication entries in `publications.html`. Each publication follows this structure:
```html
<div class="pub-item">
    <div class="pub-year">2024</div>
    <div class="pub-content">
        <h3 class="pub-title">Paper Title</h3>
        <p class="pub-authors">Authors</p>
        <p class="pub-venue">Venue</p>
        <!-- Add citation metrics and links -->
    </div>
</div>
```

### Adding Blog Posts

Add new blog cards in `blog.html`:
```html
<article class="blog-card">
    <div class="blog-image">
        <!-- Add image or placeholder -->
    </div>
    <div class="blog-info">
        <span class="blog-date">Date</span>
        <span class="blog-tag">Category</span>
    </div>
    <h3 class="blog-title">Title</h3>
    <p class="blog-excerpt">Excerpt</p>
</article>
```

## 🎨 Color Customization

To change the color scheme, edit the CSS variables in `styles.css`:
```css
:root {
    --primary-color: #2563eb;    /* Main theme color */
    --secondary-color: #1e40af;  /* Darker shade */
    --accent-color: #3b82f6;     /* Lighter shade */
    /* ... other colors */
}
```

## 📱 Social Links

Update your social media links in `index.html`:
- Google Scholar
- GitHub
- Email

## 🌐 Deployment

### GitHub Pages

1. Push this repository to GitHub
2. Go to repository Settings → Pages
3. Select "Deploy from a branch"
4. Choose the `main` branch and `/root` folder
5. Your site will be available at `https://yourusername.github.io`

### Other Hosting

Simply upload all files to any web hosting service. No server-side processing required.

## 📊 Current Statistics

- **Citations**: 42
- **h-index**: 3
- **i10-index**: 2

## 📄 License

Feel free to use this template for your own personal website.

## 👤 Contact

- **Email**: chenyu_wang@seas.harvard.edu
- **Google Scholar**: [Profile Link](https://scholar.google.com/citations?user=QI96hfoAAAAJ&hl=en)

---

Built with ❤️ using HTML, CSS, and JavaScript

