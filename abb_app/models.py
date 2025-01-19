from django.db import models

class AbbreviationEntry(models.Model):
    """Main model for abbreviation dictionary entries"""
    abbreviation = models.CharField(max_length=50, db_index=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    highlighted = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('approved', 'Approved'),
            ('for_review', 'For Review'),
            ('rejected', 'Rejected')
        ],
        default='for_review',
        db_index=True
    )
    
    class Meta:
        unique_together = ['abbreviation', 'description']
        ordering = ['abbreviation', '-created_at']
        
    def __str__(self):
        return f"{self.abbreviation} - {self.description}"